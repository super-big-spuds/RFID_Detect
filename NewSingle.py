import sys
import random
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QMainWindow, QPushButton, QVBoxLayout, 
                           QWidget, QTextEdit, QLabel, QLineEdit, QHBoxLayout,
                           QComboBox, QGridLayout)
from PyQt5.QtCore import QThread, pyqtSignal
import serial
import time

class RFIDReader(QThread):
    data_received = pyqtSignal(bytes)
    
    def __init__(self, port='COM4', baudrate=115200):
        super().__init__()
        self.serial_port = serial.Serial(port, baudrate, timeout=0.1)
        self.is_running = True

    def run(self):
        while self.is_running:
            if self.serial_port.in_waiting:
                data = self.serial_port.readline()
                if data:
                    self.data_received.emit(data)
            time.sleep(0.1)
            
    def write_data(self, data):
        try:
            self.serial_port.write(data)
            return True
        except Exception as e:
            print(f"寫入錯誤: {str(e)}")
            return False
        
    def stop(self):
        self.is_running = False
        self.serial_port.close()

def bytes_to_hex_string(data):
    """將位元組資料轉換為十六進位字串，保證每個byte都轉換"""
    return ''.join([f"{b:02X}" for b in data])

def generate_tag_id():
    """產生4碼隨機UUID"""
    return f"{random.randint(0, 0xFFFF):04X}"

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RFID 標籤管理系統")
        self.setGeometry(100, 100, 800, 600)
        self.setup_ui()

    def setup_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        form_layout = QGridLayout()

        # UUID (4碼，自動產生)
        self.tag_id = generate_tag_id()
        self.tag_id_label = QLabel(f"UUID (4碼): {self.tag_id}")
        self.regen_tag_button = QPushButton("重新產生")
        self.regen_tag_button.clicked.connect(self.regenerate_tag_id)
        form_layout.addWidget(self.tag_id_label, 0, 0)
        form_layout.addWidget(self.regen_tag_button, 0, 1)

        # 產品ID輸入 (13碼)
        form_layout.addWidget(QLabel("產品ID (13碼):"), 1, 0)
        self.product_id_input = QLineEdit()
        self.product_id_input.setPlaceholderText("輸入13位產品ID")
        form_layout.addWidget(self.product_id_input, 1, 1)

        # 年份下拉選單
        current_year = datetime.now().year
        form_layout.addWidget(QLabel("年份:"), 2, 0)
        self.year_combo = QComboBox()
        for year in range(current_year, current_year + 10):
            self.year_combo.addItem(str(year))
        form_layout.addWidget(self.year_combo, 2, 1)

        # 月份下拉選單 (01-12)
        form_layout.addWidget(QLabel("月份:"), 3, 0)
        self.month_combo = QComboBox()
        for month in range(1, 13):
            self.month_combo.addItem(f"{month:02d}")
        form_layout.addWidget(self.month_combo, 3, 1)

        # 日期下拉選單 (01-31)
        form_layout.addWidget(QLabel("日期:"), 4, 0)
        self.day_combo = QComboBox()
        for day in range(1, 32):
            self.day_combo.addItem(f"{day:02d}")
        form_layout.addWidget(self.day_combo, 4, 1)

        layout.addLayout(form_layout)

        # 按鈕區
        button_layout = QHBoxLayout()
        self.read_button = QPushButton("讀取標籤")
        self.write_button = QPushButton("寫入資料")
        button_layout.addWidget(self.read_button)
        button_layout.addWidget(self.write_button)
        layout.addLayout(button_layout)
        
        # 狀態顯示
        self.status_label = QLabel("狀態：")
        self.text_display = QTextEdit()
        self.text_display.setReadOnly(True)
        layout.addWidget(self.status_label)
        layout.addWidget(self.text_display)

        # 連接事件
        self.read_button.clicked.connect(self.read_tag)
        self.write_button.clicked.connect(self.write_tag)
        
        # 初始化RFID讀寫器
        try:
            self.rfid_reader = RFIDReader()
            self.rfid_reader.data_received.connect(self.handle_response)
            self.rfid_reader.start()
            self.status_label.setText("狀態：已連接")
        except Exception as e:
            self.status_label.setText(f"狀態：連接失敗 - {str(e)}")

    def regenerate_tag_id(self):
        """重新產生UUID"""
        self.tag_id = generate_tag_id()
        self.tag_id_label.setText(f"UUID (4碼): {self.tag_id}")

    def format_epc_data(self):
        """格式化EPC資料"""
        try:
            user_code = self.product_id_input.text().strip()
            if len(user_code) != 13 or not all(c in '0123456789ABCDEF' for c in user_code.upper()):
                raise ValueError("產品ID必須是13位十六進位數")

            year = int(self.year_combo.currentText()) % 100
            month = int(self.month_combo.currentText())
            day = int(self.day_combo.currentText())

            # 組合EPC資料: 00前綴 + 4碼UUID + 13碼產品ID + 2碼年 + 1碼月(16進制) + 2碼日
            epc = f"00{self.tag_id[:4]}{user_code[:13]}{year:02X}{month:X}{day:02X}"
            
            self.text_display.append(f"""寫入資料格式：
前綴: 00
UUID (4碼): {self.tag_id[:4]}
產品ID (13碼): {user_code[:13]}
年份: {year:02X}
月份: {month:X}
日期: {day:02X}
完整資料: {epc}""")
            
            return epc
        except ValueError as e:
            raise ValueError(f"資料格式錯誤: {str(e)}")

    def read_tag(self):
        """單次讀取標籤"""
        self.text_display.clear()
        command = bytes.fromhex("BB 00 22 00 00 22 7E")
        if self.rfid_reader.write_data(command):
            self.text_display.append("正在讀取...")
            self.status_label.setText("狀態：讀取指令已發送")
        else:
            self.text_display.append("讀取指令發送失敗！")
            self.status_label.setText("狀態：讀取失敗")

    def write_tag(self):
        """寫入EPC資料到標籤"""
        self.text_display.clear()
        
        try:
            epc_hex = self.format_epc_data()
            command_str = f"BB 00 49 00 15 00 00 00 00 01 00 02 00 06 {epc_hex}"
            self.text_display.append(f"命令(校驗和前): {command_str}")
            
            command_bytes = bytes.fromhex(command_str)
            checksum = sum(command_bytes[1:]) & 0xFF
            self.text_display.append(f"校驗和: {checksum:02X}")
            
            write_cmd = command_bytes + bytes([checksum, 0x7E])
            self.text_display.append(f"發送寫入命令: {bytes_to_hex_string(write_cmd)}")
            
            if self.rfid_reader.write_data(write_cmd):
                self.text_display.append("正在寫入...")
                self.status_label.setText("狀態：寫入指令已發送")
            else:
                self.text_display.append("寫入指令發送失敗！")
                self.status_label.setText("狀態：寫入失敗")
                
        except ValueError as e:
            self.text_display.append(f"輸入資料格式錯誤: {str(e)}")
        except Exception as e:
            self.text_display.append(f"寫入過程錯誤: {str(e)}")

    def parse_epc_data(self, epc_data):
        """解析EPC資料"""
        try:
            # 將位元組轉換為十六進位字串
            hex_str = bytes_to_hex_string(epc_data)
            
            # 找到實際資料的起始位置（跳過前導0000）
            if hex_str.startswith('0000'):
                actual_data = hex_str[4:]
            else:
                actual_data = hex_str
                
            # 確保數據長度足夠（4位UUID + 13位產品ID + 2位年 + 1位月 + 2位日 = 22位）
            if len(actual_data) < 22:
                return f"數據長度不足（需要22字符，實際{len(actual_data)}字符）\n原始資料: {hex_str}\n擷取資料: {actual_data}"
                
            # 解析各個欄位
            tag_id = actual_data[0:4]         # 4碼UUID (BD49)
            product_id = actual_data[4:17]    # 13碼產品ID (1234567890123)
            year = actual_data[17:19]         # 年份 (18)
            month = actual_data[19:20]        # 月份 (1)
            day = actual_data[20:22]          # 日期 (01)

            # 數值轉換
            year_dec = 2000 + int(year, 16)   # 年份轉換
            month_dec = int(month, 16)        # 月份轉換（16進制到十進制）
            day_dec = int(day, 16)            # 日期轉換

            return f"""原始資料: {actual_data}
    分解資料:
    - UUID (4碼): {tag_id}
    - 產品ID (13碼): {product_id}
    - 年份: {year} -> {year_dec}年
    - 月份: {month} -> {month_dec}月
    - 日期: {day} -> {day_dec}日"""
                
        except Exception as e:
            return f"解析錯誤: {str(e)}\n原始資料: {hex_str}"
    def handle_response(self, data):
        """處理接收到的RFID回應"""
        hex_str = bytes_to_hex_string(data)
        self.text_display.append(f"收到資料: {hex_str}")
        
        if len(data) > 3 and data[0] == 0xBB:
            if data[1] == 0x02:  # 標籤讀取回應
                if len(data) >= 21:  # 確保有足夠的數據長度
                    # 修改取值範圍，確保包含完整的數據（包括日期
                    for i in range(0, len(data), 26):
                        epc_data = data[i+7:i+21]
                        if(len(epc_data) > 0):
                            parsed_data = self.parse_epc_data(epc_data)
                            if parsed_data:
                                self.text_display.append("\n解析資料:")
                                self.text_display.append(parsed_data)
                    self.status_label.setText("狀態：讀取成功")
                else:
                    self.text_display.append(f"數據長度不足：收到 {len(data)} bytes")
            elif data[1] == 0x01:  # 命令執行回應
                if data[2] == 0xFF:  # 錯誤回應
                    error_code = data[6] if len(data) > 6 else 0
                    error_msg = {
                        0x09: "找不到標籤",
                        0x15: "寫入失敗",
                        0x16: "存取密碼不正確",
                        0x17: "標籤通訊錯誤",
                        0xA3: "超出晶片容量範圍"
                    }.get(error_code, f"未知錯誤(0x{error_code:02X})")
                    self.text_display.append(f"錯誤: {error_msg}")
                else:
                    self.text_display.append("命令執行成功")

    def closeEvent(self, event):
        """停止串口"""
        self.rfid_reader.stop()
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())