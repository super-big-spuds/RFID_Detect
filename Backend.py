from flask import Flask, request, jsonify
from flask_cors import CORS  # 新增這行
import serial
import random
from datetime import datetime
import time

app = Flask(__name__)
CORS(app)  # 新增這行，啟用 CORS

class RFIDController:
    def __init__(self, port='COM4', baudrate=115200):
        self.serial_port = serial.Serial(port, baudrate, timeout=1)
        
    def generate_tag_id(self):
        """產生4碼隨機UUID"""
        return f"{random.randint(0, 0xFFFF):04X}"
        
    def bytes_to_hex_string(self, data):
        """將位元組資料轉換為十六進位字串"""
        return ''.join([f"{b:02X}" for b in data])
        
    def parse_epc_data(self, epc_data):
        """解析EPC資料"""
        try:
            # 將位元組轉換為十六進位字串
            hex_str = self.bytes_to_hex_string(epc_data)
            
            # 找到實際資料的起始位置（跳過前導0000）
            if hex_str.startswith('0000'):
                actual_data = hex_str[4:]
            else:
                actual_data = hex_str
                
            # 確保數據長度足夠
            if len(actual_data) < 22:
                return {"error": f"數據長度不足（需要22字符，實際{len(actual_data)}字符）", 
                        "raw_data": hex_str}
                
            # 解析各個欄位
            tag_id = actual_data[0:4]         # 4碼UUID
            product_id = actual_data[4:17]    # 13碼產品ID
            year = actual_data[17:19]         # 年份
            month = actual_data[19:20]        # 月份
            day = actual_data[20:22]          # 日期

            # 數值轉換
            year_dec = 2000 + int(year, 16)   # 年份轉換
            month_dec = int(month, 16)        # 月份轉換（16進制到十進制）
            day_dec = int(day, 16)            # 日期轉換

            return {
                "success": True,
                "data": {
                    "tag_id": tag_id,
                    "product_id": product_id,
                    "year": year_dec,
                    "month": month_dec,
                    "day": day_dec,
                    "raw_data": actual_data
                }
            }
                
        except Exception as e:
            return {"error": str(e), "raw_data": hex_str}
            
    def read_tag(self):
        """讀取標籤"""
        try:
            # 發送讀取命令
            command = bytes.fromhex("BB 00 22 00 00 22 7E")
            self.serial_port.write(command)
            
            # 等待回應
            time.sleep(0.1)
            if self.serial_port.in_waiting:
                data = self.serial_port.read(self.serial_port.in_waiting)
                
                # 檢查回應格式
                if len(data) > 3 and data[0] == 0xBB and data[1] == 0x02:
                    if len(data) >= 21:
                        epc_data = data[7:21]
                        return self.parse_epc_data(epc_data)
                    
            return {"error": "無法讀取標籤數據"}
            
        except Exception as e:
            return {"error": f"讀取錯誤: {str(e)}"}
            
    def write_tag(self, product_id):
        """寫入標籤"""
        try:
            # 驗證產品ID格式
            if len(product_id) != 13 or not all(c in '0123456789ABCDEF' for c in product_id.upper()):
                return {"error": "產品ID必須是13位十六進位數"}

            # 生成UUID和取得當前時間
            tag_id = self.generate_tag_id()
            now = datetime.now()
            year = now.year % 100
            month = now.month
            day = now.day

            # 組合EPC資料
            epc = f"00{tag_id}{product_id}{year:02X}{month:X}{day:02X}"
            
            # 組合寫入命令
            command_str = f"BB 00 49 00 15 00 00 00 00 01 00 02 00 06 {epc}"
            command_bytes = bytes.fromhex(command_str)
            checksum = sum(command_bytes[1:]) & 0xFF
            write_cmd = command_bytes + bytes([checksum, 0x7E])
            
            # 發送命令
            self.serial_port.write(write_cmd)
            
            # 等待回應
            time.sleep(0.1)
            if self.serial_port.in_waiting:
                response = self.serial_port.read(self.serial_port.in_waiting)
                if len(response) > 3 and response[0] == 0xBB and response[1] == 0x01:
                    if response[2] == 0xFF:  # 錯誤回應
                        error_code = response[6] if len(response) > 6 else 0
                        error_msg = {
                            0x09: "找不到標籤",
                            0x15: "寫入失敗",
                            0x16: "存取密碼不正確",
                            0x17: "標籤通訊錯誤",
                            0xA3: "超出晶片容量範圍"
                        }.get(error_code, f"未知錯誤(0x{error_code:02X})")
                        return {"error": error_msg}
                    return {
                        "success": True,
                        "data": {
                            "tag_id": tag_id,
                            "product_id": product_id,
                            "year": now.year,
                            "month": month,
                            "day": day,
                            "epc": epc
                        }
                    }
                    
            return {"error": "寫入失敗，未收到回應"}
            
        except Exception as e:
            return {"error": f"寫入錯誤: {str(e)}"}
            
    def close(self):
        """關閉串口"""
        if self.serial_port.is_open:
            self.serial_port.close()

# 初始化RFID控制器
rfid = RFIDController()

@app.route('/write', methods=['POST'])
def write():
    """寫入標籤API"""
    try:
        data = request.get_json()
        if not data or 'product_id' not in data:
            return jsonify({"error": "缺少產品ID"}), 400
            
        result = rfid.write_tag(data['product_id'])
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/read', methods=['GET'])
def read():
    """讀取標籤API"""
    try:
        result = rfid.read_tag()
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 程式結束時關閉串口
import atexit
atexit.register(rfid.close)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)