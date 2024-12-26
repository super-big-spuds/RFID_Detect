from flask import Flask, jsonify
from flask_cors import CORS
import serial
import time
import threading
from queue import Queue

app = Flask(__name__)
CORS(app)

class RFIDController:
    def __init__(self, port='COM4', baudrate=9600):
        self.serial = None
        self.port = port
        self.baudrate = baudrate
        self.is_scanning = False
        self.scan_thread = None
        self.tag_queue = Queue()
        self.lock = threading.Lock()

    def connect(self):
        try:
            if self.serial is None or not self.serial.is_open:
                self.serial = serial.Serial(
                    port=self.port,
                    baudrate=self.baudrate,
                    timeout=1
                )
                time.sleep(0.1)
            return True
        except Exception as e:
            print(f"連接錯誤: {str(e)}")
            return False

    def send_command(self, data):
        try:
            if not self.connect():
                return False, "串口連接失敗"

            with self.lock:
                self.serial.reset_input_buffer()
                self.serial.write(bytes(data))
                time.sleep(0.1)
                response = self.serial.read(100)
                return True, response
        except Exception as e:
            print(f"發送命令錯誤: {str(e)}")
            return False, str(e)

    def calculate_checksum(self, data):
        return sum(data) & 0xFF

    def start_inventory(self):
        if self.is_scanning:
            return False, "已在掃描中"

        command = [
            0xBB,                   # Header
            0x00,                   # Type
            0x27,                   # Command
            0x00, 0x03,            # PL
            0x22,                   # Reserved
            0x27, 0x10,            # CNT
        ]
        command.append(self.calculate_checksum(command[1:]))
        command.append(0x7E)

        success, response = self.send_command(command)
        if success:
            self.is_scanning = True
            self.scan_thread = threading.Thread(target=self._scan_loop)
            self.scan_thread.daemon = True
            self.scan_thread.start()
            return True, "開始掃描"
        return False, "開始掃描失敗"

    def _scan_loop(self):
        while self.is_scanning and self.serial and self.serial.is_open:
            try:
                response = self.serial.read(100)
                if response and len(response) > 0:
                    if response[0] == 0xBB and response[-1] == 0x7E:
                        epc_data = response[8:20]
                        self.tag_queue.put(epc_data)
            except:
                pass
            time.sleep(0.1)

    def stop_inventory(self):
        if not self.is_scanning:
            return False, "未在掃描中"

        command = [
            0xBB,                   # Header
            0x01,                   # Type
            0xFF,                   # Command
            0x00, 0x01,            # PL
            0x15,                   # Parameter
        ]
        command.append(self.calculate_checksum(command[1:]))
        command.append(0x7E)

        self.is_scanning = False
        if self.scan_thread:
            self.scan_thread.join(timeout=1)
        
        success, response = self.send_command(command)
        return success, "停止掃描" if success else "停止掃描失敗"

    def get_select_param(self):
        command = [
            0xBB,                   # Header
            0x00,                   # Type
            0x0B,                   # Command
            0x00, 0x00,            # PL
        ]
        command.append(self.calculate_checksum(command[1:]))
        command.append(0x7E)

        success, response = self.send_command(command)
        return success, "獲取Select參數成功" if success else "獲取Select參數失敗"

    def set_select_param(self):
        command = [
            0xBB,                   # Header
            0x01,                   # Type
            0x0B,                   # Command
            0x00, 0x13,            # PL
            0x01,                   # SelParam
            0x00,                   # Reserved
            0x01,                   # Target/Action/MemBank
            0x00, 0x00, 0x00, 0x20, # Pointer
            0x60,                   # MaskLen
            0x00,                   # Truncate
            0x30, 0x75, 0x1F, 0xEB, # Mask
            0x70, 0x5C              # Mask
        ]
        command.append(self.calculate_checksum(command[1:]))
        command.append(0x7E)

        success, response = self.send_command(command)
        return success, "設置Select參數成功" if success else "設置Select參數失敗"

    def set_select_mode(self):
        command = [
            0xBB,                   # Header
            0x00,                   # Type
            0x12,                   # Command
            0x00, 0x01,            # PL
            0x01,                   # Mode
        ]
        command.append(self.calculate_checksum(command[1:]))
        command.append(0x7E)

        success, response = self.send_command(command)
        return success, "設置Select模式成功" if success else "設置Select模式失敗"

    def write_memory(self, data=None):
        if data is None:
            data = [0x12, 0x34, 0x56, 0x78]

        command = [
            0xBB,                   # Header
            0x00,                   # Type
            0x49,                   # Command
            0x00, 0x00,            # PL
            0x03,                   # MemBank
            0x00, 0x00,            # SA
            0x00, len(data)        # DL
        ]
        command.extend(data)
        command.append(self.calculate_checksum(command[1:]))
        command.append(0x7E)

        success, response = self.send_command(command)
        return success, "寫入記憶體成功" if success else "寫入記憶體失敗"

    def lock_memory(self):
        command = [
            0xBB,                   # Header
            0x00,                   # Type
            0x82,                   # Command
            0x00, 0x07,            # PL
            0x00, 0x00, 0xFF,      # Reserved
            0x02,                   # Lock payload
            0x02,                   # Mask
        ]
        command.append(self.calculate_checksum(command[1:]))
        command.append(0x7E)

        success, response = self.send_command(command)
        return success, "鎖定記憶體成功" if success else "鎖定記憶體失敗"

rfid = RFIDController()

@app.route('/api/inventory/start', methods=['POST'])
def start_inventory():
    success, message = rfid.start_inventory()
    return jsonify({'success': success, 'message': message})

@app.route('/api/inventory/stop', methods=['POST'])
def stop_inventory():
    success, message = rfid.stop_inventory()
    return jsonify({'success': success, 'message': message})

@app.route('/api/inventory/data', methods=['GET'])
def get_inventory_data():
    data = []
    try:
        while not rfid.tag_queue.empty():
            tag_data = rfid.tag_queue.get_nowait()
            data.append(' '.join([hex(x)[2:].zfill(2) for x in tag_data]))
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/select/get', methods=['POST'])
def get_select():
    success, message = rfid.get_select_param()
    return jsonify({'success': success, 'message': message})

@app.route('/api/select/set', methods=['POST'])
def set_select():
    success, message = rfid.set_select_param()
    return jsonify({'success': success, 'message': message})

@app.route('/api/select/mode', methods=['POST'])
def set_mode():
    success, message = rfid.set_select_mode()
    return jsonify({'success': success, 'message': message})

@app.route('/api/memory/write', methods=['POST'])
def write_memory():
    success, message = rfid.write_memory()
    return jsonify({'success': success, 'message': message})

@app.route('/api/memory/lock', methods=['POST'])
def lock_memory():
    success, message = rfid.lock_memory()
    return jsonify({'success': success, 'message': message})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)