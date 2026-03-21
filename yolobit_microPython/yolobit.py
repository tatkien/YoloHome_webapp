import network
import time
import ubinascii
import ujson as json
from yolobit import *
from machine import Pin, unique_id, I2C
from umqtt.simple import MQTTClient

display.show(Image.HAPPY)

# --- 1. CẤU HÌNH ---
WIFI_SSID = "Tên_WiFi"
WIFI_PASS = "Mật_Khẩu"
MQTT_BROKER = "x.x.x.x"
PIN_MAP = {"P0": pin0, "P1": pin1, "P2": pin2}

HARDWARE_ID = ubinascii.hexlify(unique_id()).decode()
# Các topic MQTT
TOPIC_ANNOUNCE = "smart_home/hardware/{}/announce".format(HARDWARE_ID)
TOPIC_SENSOR   = "smart_home/hardware/{}/sensor".format(HARDWARE_ID)
TOPIC_COMMAND  = "smart_home/hardware/{}/command".format(HARDWARE_ID)
TOPIC_STATE    = "smart_home/hardware/{}/state".format(HARDWARE_ID)

i2c = I2C(0, scl=Pin(19), sda=Pin(20))
servo_p12 = PWM(Pin(pin12.pin), freq=50)

# --- 2. DRIVER & QUẢN LÝ KẾT NỐI ---
class DHT20:
    def __init__(self, i2c):
        self.i2c = i2c
        self.addr = 0x38
    def read(self):
        try:
            self.i2c.writeto(self.addr, b'\xac\x33\x00')
            time.sleep_ms(80)
            data = self.i2c.readfrom(self.addr, 7)
            hum = ((data[1] << 12) | (data[2] << 4) | (data[3] >> 4)) * 100 / 1048576
            temp = (((data[3] & 0x0F) << 16) | (data[4] << 8) | data[5]) * 200 / 1048576 - 50
            return int(round(temp)), int(round(hum))
        except Exception as e: 
            print("Lỗi đọc DHT20:", e)
            return None, None

dht = DHT20(i2c)
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
client = MQTTClient(HARDWARE_ID, MQTT_BROKER)

#Tự kết nối
mqtt_connected = False
last_reconnect_attempt = 0

#Servo
servo_is_open = False
open_start_time = 0

def quay_servo(goc):
    # Biến đổi từ GÓC sang DUTY
    goc = int(goc)
    if goc < 0: goc = 0
    if goc > 180: goc = 180

    gia_tri_duty = int((goc / 180) * 102 + 26)
    servo_p12.duty(gia_tri_duty)
    print(f"Servo -> {goc} độ (Duty: {gia_tri_duty})")

def sub_cb(topic, msg):
    """Xử lý lệnh JSON"""
    global servo_is_open, open_start_time
    try:
        data = json.loads(msg)
        pin_name = data.get("pin")
        value = data.get("value", 90)
        trang_thai = data.get("isOn", False)
        
        # TRƯỜNG HỢP 1: ĐIỀU KHIỂN SERVO (LOCK)
        if pin_name == "servo":
            if trang_thai:
                quay_servo(value)      # Mở cửa
                servo_is_open = True
                open_start_time = time.ticks_ms() # 5s
            else:
                quay_servo(0)          # Đóng cửa ngay lập tức
                servo_is_open = False
            
            print(f"Lệnh Servo: {trang_thai}, Góc: {value}")
            
        # TRƯỜNG HỢP 2: ĐIỀU KHIỂN CÁC CHÂN P0, P1, P2 (Đèn/Quạt)
        elif pin_name in PIN_MAP:
            target_pin = PIN_MAP[pin_name]
            if not trang_thai: 
                target_pin.write_analog(0)
            else:
                pwm_levels = {1: 400, 2: 700, 3: 1023}
                power = pwm_levels.get(value, 1023) 
                target_pin.write_analog(power)
            print(f"Đã điều khiển {pin_name} -> {'ON' if trang_thai else 'OFF'}")

            # 2. Gửi phản hồi lại Server sau khi thực hiện xong
        feedback = {
            "pin": pin_name,
            "isOn": trang_thai,
            "value": value,
            "status": "success"
        }
        client.publish(TOPIC_STATE, json.dumps(feedback))
        
    except Exception as e: 
        print("Lỗi xử lý JSON hoặc Điều khiển:", e)

def get_announce_payload():
    data = {
        "name": "Yolobit_{}".format(HARDWARE_ID),
        "pins": ["temp", "humi", "servo", "P0", "P1", "P2"] 
    }
    return json.dumps(data)

def ensure_connectivity():
    global mqtt_connected, last_reconnect_attempt
    curr_time = time.ticks_ms()

    # Nếu WiFi mất, thử kết nối lại
    if not wlan.isconnected():
        mqtt_connected = False
        if time.ticks_diff(curr_time, last_reconnect_attempt) > 5000:
            print("Đang thử kết nối lại WiFi...")
            wlan.connect(WIFI_SSID, WIFI_PASS)
            last_reconnect_attempt = curr_time
        return False

    # Nếu WiFi OK nhưng MQTT chưa kết nối
    if not mqtt_connected:
        if time.ticks_diff(curr_time, last_reconnect_attempt) > 5000:
            try:
                print("🔌 Đang thử kết nối lại MQTT Broker...")
                # Đóng socket cũ
                try:
                    client.sock.close()
                except: pass 
                
                client.connect()
                client.sock.settimeout(0.5)
                client.subscribe(TOPIC_COMMAND)
                client.publish(TOPIC_ANNOUNCE, get_announce_payload())
                mqtt_connected = True
                print("Đã kết nối lại Server!")
            except Exception as e:
                print("Lỗi kết nối Broker, sẽ thử lại. Chi tiết:", e)
                mqtt_connected = False
            last_reconnect_attempt = curr_time
    
    return mqtt_connected

# --- 3. CHƯƠNG TRÌNH CHÍNH ---
last_sensor_send = 0
last_sensor_read = 0
temp, humi = 0, 0

print("Hệ thống đang khởi động...")

while True:
    now = time.ticks_ms()

    if servo_is_open:
        if time.ticks_diff(now, open_start_time) > 5000:
            print("Hết 5 giây, tự động khoá cửa...")
            quay_servo(0)
            servo_is_open = False
    
    # 1. Đọc cảm biến mỗi 2 giây
    if time.ticks_diff(now, last_sensor_read) > 2000:
        temp, humi = dht.read()
        last_sensor_read = now

    # 2. Kiểm tra và tự động kết nối lại
    is_ready = ensure_connectivity()

    if is_ready:
        try:
            # 3. Kiểm tra lệnh từ Server
            client.check_msg()

            # 4. Gửi dữ liệu định kỳ mỗi 10 giây
            if time.ticks_diff(now, last_sensor_send) > 10000:

                if temp is not None and humi is not None:
                    payload = json.dumps({"temp": temp, "humi": humi})
                    client.publish(TOPIC_SENSOR, payload)
                    print("Gửi dữ liệu:", payload)
                else:
                    print("Bỏ qua lượt gửi do lỗi cảm biến")
                
                last_sensor_send = now
        except Exception as e:
            print("Mất kết nối MQTT trong khi chạy:", e)
            mqtt_connected = False 

    time.sleep_ms(200)