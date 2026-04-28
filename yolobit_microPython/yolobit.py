import network, time, ubinascii
import ujson as json
from machine import Pin, unique_id, SoftI2C, WDT
from yolobit import *
from neopixel import NeoPixel

try:
    from umqtt.robust import MQTTClient
    HAS_MQTT_LIB = True
except ImportError:
    HAS_MQTT_LIB = False
    print("[ERROR] No MQTT Library")

# NUÔI CHÓ
wdt = WDT(timeout=20000)

# KHỞI TẠO CHÂN
display.show(Image.HEART)
i2c = SoftI2C(scl=Pin(22), sda=Pin(21)) 
rgb = RGBLed(13, 4)
pin12.servo_write(0)
PIN_MAP = {"P0": pin0, "P1": pin1, "P2": pin2}
for pin_name in PIN_MAP: PIN_MAP[pin_name].write_analog(0)

WIFI_SSID, WIFI_PASS = "G35", "12345678"
MQTT_BROKER = "10.23.151.71"
ID = ubinascii.hexlify(unique_id()).decode()

# Topics
TOPIC_ANNOUNCE = f"smart_home/hardware/{ID}/announce"
TOPIC_SEN = f"smart_home/hardware/{ID}/sensor"
TOPIC_COM = f"smart_home/hardware/{ID}/command"
TOPIC_STA = f"smart_home/hardware/{ID}/state"

# STATE MACHINE
# Trạng thái WiFi
W_DISCONNECTED, W_WAITING_ACTIVATE, W_CONNECTING, W_CONNECTED = 0, 1, 2, 3
wifi_state = W_DISCONNECTED
wifi_timer = 0

# Trạng thái MQTT
M_IDLE, M_CONNECTING, M_SUBSCRIBING, M_ANNOUNCING, M_READY = 0, 1, 2, 3, 4
mqtt_state = M_IDLE
mqtt_timer = 0
mqtt_setup_done = False

# CLASS SENSOR DHT20
class DHT20:
    def __init__(self, i2c, address=0x38):
        self.i2c = i2c
        self.address = address
        self._temp, self._humi = 0, 0
        self.is_collecting = False
        self.start_time = 0
        time.sleep_ms(500)
        try:
            if not self.is_ready():
                self.reset_register()
                time.sleep_ms(10)
        except Exception as e:
            print("[ERROR] Init DHT20:", e)
            
    def _get_status(self):
        try: return self.i2c.readfrom(self.address, 1)[0]
        except:  return 0
            
    def is_ready(self):
        return (self._get_status() & 0x08) == 0x08
    
    def reset_register(self):
        try: self.i2c.writeto(self.address, b'\xbe\x08\x00')
        except:  pass
    
    def trigger_measurement(self):
        if not self.is_ready():
            self.reset_register()
            print("[WARNING] DHT20: Re-calibrating...")
            return False 

        try:
            self.i2c.writeto(self.address, b'\xac\x33\x00')
            self.start_time = time.ticks_ms()
            self.is_collecting = True
            return True
        except: return False
        
    def collect_data(self):
        if not self.is_collecting: return False 
        status = self._get_status()
        # Kiểm tra Bit 7 (Busy bit)
        if (status & 0x80) == 0:
            try:
                data = self.i2c.readfrom(self.address, 7)          
                # Tính toán độ ẩm 20-bit
                hraw = ((data[1] << 12) | (data[2] << 4) | (data[3] >> 4))
                self._humi = hraw * 100 / 1048576 
                # Tính toán nhiệt độ 20-bit
                traw = (((data[3] & 0x0F) << 16) | (data[4] << 8) | data[5])
                self._temp = traw * 200 / 1048576 - 50          
                self.is_collecting = False
                return True 
            except Exception as e:
                print("[ERROR] Read DHT20:", e)
                self.is_collecting = False
        if time.ticks_diff(time.ticks_ms(), self.start_time) > 200:
            self.is_collecting = False            
        return False
    
    def temp(self): return round(self._temp, 1)
    def humi(self): return round(self._humi, 1)

class RGBLed:
    def __init__(self, pin, num_leds):
        self._np = NeoPixel(Pin(pin), num_leds)
        self._num_leds = num_leds

    def show(self, index, color):
        if index == 0:
            for i in range(self._num_leds):
                self._np[i] = color
        elif 0 < index <= self._num_leds:
            self._np[index - 1] = color
        self._np.write()

# KHỞI TẠO, VÒNG LẬP CHÍNH
dht = None
try: dht = DHT20(i2c)
except: print("No DHT20")
servo_is_open, open_start_time = False, 0
last_dht_trigger, last_display_time = 0, 0

# --- HÀM HELPER ---
def set_servo(angle, is_on):
    """Điều khiển servo của Yolobit"""
    target_angle = angle if is_on else 0
    pin12.servo_write(target_angle)
    return is_on

def set_pwm_pin(pin_obj, val, is_on):
    """Tính mức cho quạt"""
    if not is_on:
        power = 0
    else:
        level = {1: 555, 2: 777, 3: 1023}
        power = max(0, min(1023, level.get(val, val)))
    pin_obj.write_analog(power)

# --- HÀM XỬ LÝ LỆNH COMMAND VÀ PHẢN HỒI LẠI ---        
def sub_cb(topic, msg):
    global servo_is_open, open_start_time, last_display_time
    try:
        data = json.loads(msg)
        pn = data.get("pin")
        val = int(data.get("value", 0))
        stat = data.get("is_on", False)
        curr_status = "error"

        # Điều khiển servo
        if pn == "servo":
            servo_is_open = stat
            pin12.servo_write(val if stat else 0)
            if stat: open_start_time = time.ticks_ms()
            curr_status = "success"

        # Điều khiển đèn/quạt
        elif pn in PIN_MAP:
            set_pwm_pin(PIN_MAP[pn], val, stat)
            curr_status = "success"
        
        elif pn in ["L1", "L2", "L3", "L4"]:
            if stat:
                if val == 1023:
                    # Màu xanh dương, đỏ, vàng, xanh lá, cho 4 đèn
                    colors = {"L1": (0, 0, 255), "L2": (255, 0, 0), "L3": (255, 255, 0), "L4": (0, 255, 0)}
                    color = colors.get(pn, (255, 255, 255))
                else:
                    b = int(val / 4)
                    color = (b, b, b)
            else:
                color = (0, 0, 0) # Tắt đèn
            
            # Gửi lệnh ra mạch LED
            idx = int(pn[1:]) 
            rgb.show(idx, color)
            curr_status = "success"

        if curr_status == "success": 
            display.show(Image.YES)
        else: 
            display.show(Image.NO)

        last_display_time = time.ticks_ms()
        payload = {"pin": pn, "is_on": stat, "value": val, "status": curr_status}
        client.publish(TOPIC_STA, json.dumps(payload))
    
    except Exception as e:
        display.show(Image.SAD)
        print("[ERROR] MQTT Callback:", e)

    # --- 5. NETWORK CONNECTION ---
wlan = network.WLAN(network.STA_IF)
if HAS_MQTT_LIB:
    client = MQTTClient(ID, MQTT_BROKER)
    client.set_callback(sub_cb)

def manage_wifi_async(now):
    global wifi_state, wifi_timer
    if not wlan.isconnected():
        if wifi_state == W_CONNECTED or wifi_state == W_DISCONNECTED:
            wlan.active(False)
            wifi_timer = now
            wifi_state = W_WAITING_ACTIVATE
            print("[WIFI] Mất kết nối, đang thử lại...")
        elif wifi_state == W_WAITING_ACTIVATE:
            if time.ticks_diff(now, wifi_timer) > 500:
                try:
                    wlan.active(True)
                    wlan.connect(WIFI_SSID, WIFI_PASS)
                except: pass
                wifi_state = W_CONNECTING
                wifi_timer = now
        elif wifi_state == W_CONNECTING:
            if time.ticks_diff(now, wifi_timer) > 10000: # Timeout sau 10s
                wifi_state = W_DISCONNECTED
    else:
        if wifi_state != W_CONNECTED:
            print("[WIFI] Đã kết nối!")
            wifi_state = W_CONNECTED

def manage_mqtt_async(now):
    global mqtt_state, mqtt_timer, mqtt_setup_done
    if not HAS_MQTT_LIB or not wlan.isconnected():
        mqtt_state, mqtt_setup_done = M_IDLE, False
        return

    if mqtt_state == M_IDLE:
        mqtt_state = M_CONNECTING
        mqtt_timer = now - 5001
    elif mqtt_state == M_CONNECTING:
        if time.ticks_diff(now, mqtt_timer) > 5000:
            try:
                if client.connect() == 0: mqtt_state = M_SUBSCRIBING
            except Exception as e:
                print("[MQTT] Connect Retry...", e)
            mqtt_timer = now
    elif mqtt_state == M_SUBSCRIBING:
        try:
            client.subscribe(TOPIC_COM)
            mqtt_state = M_ANNOUNCING
        except Exception as e:
            mqtt_state = M_CONNECTING
    elif mqtt_state == M_ANNOUNCING:
        try:
            ann = {
                "name": f"Yolobit_{ID}",
                "pins": [
                    {"pin": "temp", "type": "temp_sensor"},
                    {"pin": "humi", "type": "humidity_sensor"},
                    {"pin": "servo", "type": "lock"},
                    {"pin": "P0", "type": "unknown"},
                    {"pin": "P1", "type": "unknown"},
                    {"pin": "P2", "type": "unknown"},
                    {"pin": "L1", "type": "light"},
                    {"pin": "L2", "type": "light"},
                    {"pin": "L3", "type": "light"},
                    {"pin": "L4", "type": "light"}
                ]
            }
            client.publish(TOPIC_ANNOUNCE, json.dumps(ann))
            mqtt_state, mqtt_setup_done = M_READY, True
            print("[MQTT] Ready & announce with pin types")
        except Exception as e:
            mqtt_state = M_CONNECTING
    elif mqtt_state == M_READY:
        try:
            client.check_msg()
        except Exception as e:
            print("[MQTT] Broker disconnected:", e)
            mqtt_state, mqtt_setup_done = M_IDLE, False

while True:
    now = time.ticks_ms()
    wdt.feed()

    # Chạy tiến trình mạng 
    manage_wifi_async(now)
    manage_mqtt_async(now)
    
    # Local: Auto-close servo
    if servo_is_open and time.ticks_diff(now, open_start_time) > 8000:
        servo_is_open = set_servo(0, False)
        if mqtt_setup_done:
            try:
                payload = {"pin": "servo", "is_on": False, "value": 0, "status": "success"}
                client.publish(TOPIC_STA, json.dumps(payload))
            except:
                print("[ERROR] MQTT Publish Failed")

    # Nút nhấn A để mở khóa (demo)
    if button_a.is_pressed():
        servo_is_open = set_servo(90, True)
        open_start_time = now
        last_display_time = now
        display.show(Image.YES)
        if mqtt_setup_done:
            try:
                payload = {"pin": "servo", "is_on": True, "value": 90, "status": "success"}
                client.publish(TOPIC_STA, json.dumps(payload))
            except:
                print("[ERROR] MQTT Publish Failed")
     
    # SENSOR MANAGEMENT
    if dht and not dht.is_collecting and time.ticks_diff(now, last_dht_trigger) > 10000:
        last_dht_trigger = now
        if dht.trigger_measurement(): 
            print("[INFO] Cam bien dang do...")
        else:
            print("[WARNING] DHT20 khong gui duoc lenh do")

    if dht and dht.is_collecting and dht.collect_data():
        print(f"[INFO] Sensor: {dht.temp()}oC, {dht.humi()}%")
        if mqtt_setup_done:
            try: 
                payload = {"temp": dht.temp(), "humi": dht.humi()}
                client.publish(TOPIC_SEN, json.dumps(payload))
            except: pass

    # Báo mạch còn sống
    if time.ticks_diff(now, last_display_time) > 2000:
        display.show(Image.HEART)
    
    time.sleep_ms(20)
