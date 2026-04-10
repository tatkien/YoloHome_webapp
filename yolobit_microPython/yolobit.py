import network, time, ubinascii
import ujson as json
from yolobit import *
from machine import Pin, unique_id, SoftI2C, PWM

try:
    from umqtt.robust import MQTTClient
    HAS_MQTT_LIB = True
except:
    HAS_MQTT_LIB = False
    print("Thiếu umqtt.robust")

# --- 2. CLASS DHT20 ---
class DHT20:
    def __init__(self, i2c, address=0x38):
        self.i2c = i2c
        self.address = address
        self._temp, self._humi = 0, 0
        time.sleep_ms(500)
        try: self.reset_register()
        except: pass

    def is_ready(self):
        try:
            status = self.i2c.readfrom(self.address, 1)[0]
            return (status & 0x08) == 0x08
        except: return False

    def reset_register(self):
        try: self.i2c.writeto(self.address, b'\xbe\x08\x00')
        except: pass

    def read(self):
        self.i2c.writeto(self.address, b'\xac\x33\x00')
        for _ in range(10):
            time.sleep_ms(30)
            status = self.i2c.readfrom(self.address, 1)[0]
            if (status & 0x80) == 0: break
        
        data = self.i2c.readfrom(self.address, 7)
        hraw = ((data[1] << 12) | (data[2] << 4) | (data[3] >> 4))
        self._humi = hraw * 100 / 1048576
        traw = (((data[3] & 0x0F) << 16) | (data[4] << 8) | data[5])
        self._temp = traw * 200 / 1048576 - 50

    def temp(self): return round(self._temp, 1)
    def humi(self): return round(self._humi, 1)

# --- 3. CẤU HÌNH ---
WIFI_SSID, WIFI_PASS = "G35", "12345678"
MQTT_BROKER = "10.23.151.71" 

ID = ubinascii.hexlify(unique_id()).decode()
TOPIC_ANNOUNCE = f"smart_home/hardware/{ID}/announce"
TOPIC_SEN = f"smart_home/hardware/{ID}/sensor"
TOPIC_COM = f"smart_home/hardware/{ID}/command"
TOPIC_STA = f"smart_home/hardware/{ID}/state"

# KHỞI TẠO PHẦN CỨNG
display.show(Image.HEART)
i2c = SoftI2C(scl=Pin(22), sda=Pin(21)) 
servo_p12 = PWM(Pin(pin12.pin), freq=50)
servo_p12.duty(int((0 / 180) * 102 + 26))
PIN_MAP = {"P0": pin0, "P1": pin1, "P2": pin2}

dht_sensor = None
try:
    dht_sensor = DHT20(i2c)
    print("DHT20: OK")
except:
    print("DHT20: Không tìm thấy")

servo_is_open = False
open_start_time = 0
last_sensor_send = 0
last_wifi_attempt = 0
last_display_time = 0
mqtt_setup_done = False

# --- 4. MQTT CALLBACK ---
def sub_cb(topic, msg):
    global servo_is_open, open_start_time, last_display_time
    try:
        data = json.loads(msg)
        pn = data.get("pin")
        val = data.get("value", 0)
        stat = data.get("isOn", False)

        current_status = "error"
        if pn == "servo":
            duty = int(((val if stat else 0) / 180) * 102 + 26)
            servo_p12.duty(duty)
            if stat:
                display.show(Image.ARROW_N)
                servo_is_open, open_start_time = True, time.ticks_ms()
            else:
                display.show(Image.ARROW_S)
                servo_is_open = False
            current_status = "success"

        elif pn in PIN_MAP:
            target = PIN_MAP[pn]
            # Tính mức độ PWM (Quạt 1,2,3 hoặc Đèn 0/1023)
            power = {1: 450, 2: 700, 3: 1023}.get(val, val) if stat else 0
            target.write_analog(power)
            current_status = "success"
            display.show(Image.YES)

        if current_status == "error":
            display.show(Image.NO)

        state_msg = {
            "pin": pn,
            "isOn": stat,
            "value": val,
            "status": current_status
        }

        last_display_time = time.ticks_ms()
        client.publish(TOPIC_STA, json.dumps(state_msg))
    
    except Exception as e:
        display.show(Image.SAD)
        last_display_time = time.ticks_ms()
        print("Lỗi:", e)

# --- 5. KẾT NỐI MẠNG ---
wlan = network.WLAN(network.STA_IF)

if HAS_MQTT_LIB:
    client = MQTTClient(ID, MQTT_BROKER)
    client.set_callback(sub_cb)
    client.DEBUG = True

def safe_wifi_connect():
    print(f"--- Đang thử kết nối WiFi: {WIFI_SSID} ---")
    try:
        wlan.active(False)
        time.sleep_ms(500)
        wlan.active(True)
        wlan.connect(WIFI_SSID, WIFI_PASS)
    except Exception as e:
        print("Lỗi khởi động WiFi:", e)

safe_wifi_connect()

# --- 6. VÒNG LẶP CHÍNH ---
while True:
    now = time.ticks_ms()

    if time.ticks_diff(now, last_display_time) > 2000:
        display.show(Image.HEART)

    # Tự động đóng khoá sau 5s
    if servo_is_open and time.ticks_diff(now, open_start_time) > 8000:
        servo_p12.duty(int((0 / 180) * 102 + 26))
        servo_is_open = False
        display.show(Image.ARROW_S) 
        last_display_time = now

    # 7. ĐIỀU KHIỂN TẠI CHỖ (Nút bấm A/B)
    if button_a.was_pressed():
        servo_p12.duty(int((90 / 180) * 102 + 26)) # Mở khoá
        servo_is_open, open_start_time = True, time.ticks_ms()
        display.show(Image.ARROW_N)
        last_display_time = now
        if wlan.isconnected() and mqtt_setup_done:
            msg = {"pin": "servo", "isOn": True, "value": 90, "status": "success"}
            client.publish(TOPIC_STA, json.dumps(msg))

    if button_b.was_pressed():
        servo_p12.duty(int((0 / 180) * 102 + 26)) # Đóng khoá
        servo_is_open = False
        display.show(Image.ARROW_S)
        last_display_time = now
        if wlan.isconnected() and mqtt_setup_done:
            msg = {"pin": "servo", "isOn": False, "value": 0, "status": "success"}
            client.publish(TOPIC_STA, json.dumps(msg))

    # QUẢN LÝ KẾT NỐI
    if not wlan.isconnected():
        mqtt_setup_done = False
        if wlan.status() != network.STAT_CONNECTING:
            if time.ticks_diff(now, last_wifi_attempt) > 5000:
                safe_wifi_connect()
                last_wifi_attempt = now
    else:
        try:
            if HAS_MQTT_LIB:
                if not mqtt_setup_done:
                    client.connect()
                    client.subscribe(TOPIC_COM)
                    
                    # --- JSON ANNOUNCE ---
                    announce_data = {
                        "name": f"Yolobit_{ID}",
                        "pins": ["temp", "humi", "servo", "P0", "P1", "P2"]
                    }
                    client.publish(TOPIC_ANNOUNCE, json.dumps(announce_data))
                    
                    mqtt_setup_done = True
                    print("Đã online MQTT & Gửi Announce")

                try:
                    client.check_msg()
                except Exception as e:
                    print("Mất kết nối MQTT:", e)
                    mqtt_setup_done = False

                # Gửi dữ liệu cảm biến mỗi 10 giây
                if time.ticks_diff(now, last_sensor_send) > 10000:
                    if dht_sensor:
                        try:
                            dht_sensor.read()
                            p = json.dumps({"temp": dht_sensor.temp(), "humi": dht_sensor.humi()})
                            client.publish(TOPIC_SEN, p)
                            print(f"Gửi Sensor: {dht_sensor.temp()}°C | Độ ẩm: {dht_sensor.humi()}%")
                        except: print("Lỗi đọc cảm biến")
                    last_sensor_send = now

        except Exception as e:
            print("Đợi Broker...")
            mqtt_setup_done = False