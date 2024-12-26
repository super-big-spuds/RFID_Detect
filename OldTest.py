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
            print(f"写入错误: {str(e)}")
            return False
        
    def stop(self):
        self.is_running = False
        self.serial_port.close()

def bytes_to_hex_string(data):
    """将字节数据转换为十六进制字符串"""
    return ' '.join([f"{b:02X}" for b in data])

def generate_tag_id():
    """生成随机标签ID"""
    return f"{random.randint(0, 0xFFFFFF):06X}"

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RFID 标签批量管理系统")
        self.setGeometry(100, 100, 800, 600)

        # 创建主窗口和布局
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        # 创建分组布局
        form_layout = QGridLayout()

        # 标签ID（自动生成）
        self.tag_id = generate_tag_id()
        self.tag_id_label = QLabel(f"标签ID: {self.tag_id}")
        self.regen_tag_button = QPushButton("重新生成")
        self.regen_tag_button.clicked.connect(self.regenerate_tag_id)
        form_layout.addWidget(self.tag_id_label, 0, 0)
        form_layout.addWidget(self.regen_tag_button, 0, 1)

        # 产品ID输入
        form_layout.addWidget(QLabel("产品ID:"), 1, 0)
        self.product_id_input = QLineEdit()
        self.product_id_input.setPlaceholderText("输入8位产品ID (例如: 12345678)")
        form_layout.addWidget(self.product_id_input, 1, 1)

        # 日期选择
        # 年份下拉框 (从当前年份开始往后10年)
        current_year = datetime.now().year
        form_layout.addWidget(QLabel("年份:"), 2, 0)
        self.year_combo = QComboBox()
        for year in range(current_year, current_year + 10):
            self.year_combo.addItem(str(year))
        form_layout.addWidget(self.year_combo, 2, 1)

        # 月份下拉框 (01-12)
        form_layout.addWidget(QLabel("月份:"), 3, 0)
        self.month_combo = QComboBox()
        for month in range(1, 13):
            self.month_combo.addItem(f"{month:02d}")
        form_layout.addWidget(self.month_combo, 3, 1)

        # 日期下拉框 (01-31)
        form_layout.addWidget(QLabel("日期:"), 4, 0)
        self.day_combo = QComboBox()
        for day in range(1, 32):
            self.day_combo.addItem(f"{day:02d}")
        form_layout.addWidget(self.day_combo, 4, 1)

        # 状态下拉框
        form_layout.addWidget(QLabel("状态:"), 5, 0)
        self.status_combo = QComboBox()
        self.status_combo.addItem("未售出 (01)", "01")
        self.status_combo.addItem("已售出 (02)", "02")
        self.status_combo.addItem("被退货 (03)", "03")
        self.status_combo.addItem("报废 (04)", "04")
        form_layout.addWidget(self.status_combo, 5, 1)

        # 添加多标签操作按钮
        multi_tag_layout = QHBoxLayout()
        self.multi_read_button = QPushButton("批量读取")
        self.stop_read_button = QPushButton("停止读取")
        self.multi_write_button = QPushButton("批量写入")
        self.stop_write_button = QPushButton("停止写入")
        
        multi_tag_layout.addWidget(self.multi_read_button)
        multi_tag_layout.addWidget(self.stop_read_button)
        multi_tag_layout.addWidget(self.multi_write_button)
        multi_tag_layout.addWidget(self.stop_write_button)
        
        # 初始状态
        self.stop_read_button.setEnabled(False)
        self.stop_write_button.setEnabled(False)
        
        # 添加到主布局
        layout.addLayout(form_layout)
        layout.addLayout(multi_tag_layout)
        
        # 创建状态显示区域
        self.status_label = QLabel("状态：")
        self.text_display = QTextEdit()
        self.text_display.setReadOnly(True)
        layout.addWidget(self.status_label)
        layout.addWidget(self.text_display)

        # 记录已处理的标签
        self.processed_tags = set()
        self.is_multi_reading = False
        self.is_multi_writing = False

        # 连接按钮信号
        self.multi_read_button.clicked.connect(self.start_multi_read)
        self.stop_read_button.clicked.connect(self.stop_multi_read)
        self.multi_write_button.clicked.connect(self.start_multi_write)
        self.stop_write_button.clicked.connect(self.stop_multi_write)

        # 初始化RFID读写器
        try:
            self.rfid_reader = RFIDReader()
            self.rfid_reader.data_received.connect(self.handle_response)
            self.rfid_reader.start()
            self.status_label.setText("状态：已连接")
        except Exception as e:
            self.status_label.setText(f"状态：连接失败 - {str(e)}")

    def regenerate_tag_id(self):
        """重新生成标签ID"""
        self.tag_id = generate_tag_id()
        self.tag_id_label.setText(f"标签ID: {self.tag_id}")

    def start_multi_read(self):
        """开始批量读取"""
        self.text_display.clear()
        self.processed_tags.clear()
        self.is_multi_reading = True
        
        # 发送多次轮询命令：BB 00 27 00 03 22 FF FF 4A 7E
        command = bytes.fromhex("BB 00 27 00 03 22 FF FF 4A 7E")
        if self.rfid_reader.write_data(command):
            self.text_display.append("开始批量读取...")
            self.multi_read_button.setEnabled(False)
            self.stop_read_button.setEnabled(True)
            self.status_label.setText("状态：批量读取中")
        else:
            self.text_display.append("批量读取指令发送失败！")

    def stop_multi_read(self):
        """停止批量读取"""
        # 发送停止多次轮询命令：BB 00 28 00 00 28 7E
        command = bytes.fromhex("BB 00 28 00 00 28 7E")
        if self.rfid_reader.write_data(command):
            self.text_display.append("正在停止批量读取...")
        self.is_multi_reading = False
        self.multi_read_button.setEnabled(True)
        self.stop_read_button.setEnabled(False)

    def start_multi_write(self):
        """开始批量连续写入"""
        if not self.product_id_input.text().strip():
            self.text_display.append("请先输入产品ID！")
            return

        self.text_display.clear()
        self.processed_tags.clear()
        self.is_multi_writing = True
        
        # 使用多次轮询命令进行连续读取
        command = bytes.fromhex("BB 00 27 00 03 22 FF FF 4A 7E")
        if self.rfid_reader.write_data(command):
            self.text_display.append("开始连续写入模式...")
            self.multi_write_button.setEnabled(False)
            self.stop_write_button.setEnabled(True)
            self.status_label.setText("状态：连续写入中")
            self.text_display.append("请将标签放入读写区域，系统将自动写入...")
        else:
            self.text_display.append("连续写入启动失败！")

    def stop_multi_write(self):
        """停止批量写入"""
        command = bytes.fromhex("BB 00 28 00 00 28 7E")
        if self.rfid_reader.write_data(command):
            self.text_display.append("正在停止批量写入...")
        self.is_multi_writing = False
        self.multi_write_button.setEnabled(True)
        self.stop_write_button.setEnabled(False)

    def format_epc_data(self):
        """格式化EPC数据"""
        try:
            # 检查产品ID格式
            product_id = self.product_id_input.text().strip()
            if len(product_id) != 8 or not all(c in '0123456789ABCDEF' for c in product_id.upper()):
                raise ValueError("产品ID必须是8位十六进制数")

            # 获取年份后两位并转换为十六进制
            year = int(self.year_combo.currentText()) % 100
            month = int(self.month_combo.currentText())
            day = int(self.day_combo.currentText())
            status = self.status_combo.currentData()  # 获取状态码

            # 组合EPC数据：固定前缀(00) + 标签ID + 产品ID + 年月日 + 状态
            epc = f"00{self.tag_id}{product_id}{year:02X}{month:02X}{day:02X}{status}"
            
            # 显示debug信息
            self.text_display.append(f"""写入数据格式：
标签ID: {self.tag_id}
产品ID: {product_id}
日期: {year:02X}-{month:02X}-{day:02X}
状态: {status}
完整数据: {epc}""")
            
            return epc
        except ValueError as e:
            raise ValueError(f"数据格式错误: {str(e)}")

    def handle_multi_write_response(self, epc_data):
        """处理连续写入模式下的标签"""
        epc_str = bytes_to_hex_string(epc_data)
        
        # 检查是否已处理过这个标签
        if epc_str not in self.processed_tags:
            self.text_display.append(f"\n检测到新标签：{epc_str}")
            
            try:
                # 获取格式化的EPC数据
                epc_hex = self.format_epc_data()
                
                # 构造写入命令
                command_str = f"BB 00 49 00 15 00 00 00 00 01 00 02 00 06 {epc_hex}"
                command_bytes = bytes.fromhex(command_str)
                checksum = sum(command_bytes[1:]) & 0xFF
                write_cmd = command_bytes + bytes([checksum, 0x7E])
                
                # 发送写入命令
                if self.rfid_reader.write_data(write_cmd):
                    self.text_display.append("正在写入标签数据...")
                    # 添加到已处理列表
                    self.processed_tags.add(epc_str)
                    self.text_display.append(f"已处理标签数：{len(self.processed_tags)}")
                
            except Exception as e:
                self.text_display.append(f"写入过程出错: {str(e)}")

    def parse_epc_data(self, epc_data):
        """解析EPC資料，跳過前導30 00"""
        try:
            epc_str = bytes_to_hex_string(epc_data).replace(" ", "")
            
            # 檢查總長度是否足夠（跳過前導30 00後應為20位）
            if len(epc_str) != 24:
                return f"解析錯誤：EPC資料長度不正確 (預期24位, 實際{len(epc_str)}位)\n原始資料: {epc_str}"

            # 跳過前導30 00，從第5位開始解析
            # epc_str索引從0開始
            tag_id = epc_str[4:10]        # 標籤ID (3字節)
            product_id = epc_str[10:18]   # 產品ID (4字節)
            year = epc_str[18:20]         # 年份 (1字節)
            month = epc_str[20:22]        # 月份 (1字節)
            day = epc_str[22:24]          # 日期 (1字節)
            status = epc_str[-2:]         # 狀態 (1字節，取最後兩位)

            # 十六進制轉換為十進制顯示
            year_dec = 2000 + int(year, 16)    # 修正年份計算
            month_dec = int(month, 16)
            day_dec = int(day, 16)

            # 狀態代碼對應說明
            status_desc = {
                "01": "未售出",
                "02": "已售出", 
                "03": "退貨",
                "04": "報廢"
            }.get(status, f"未知狀態代碼({status})")

            return f"""原始資料: {epc_str}
分解資料:
- 標籤ID: {tag_id}
- 產品ID: {product_id}
- 年份編碼: {year} -> {year_dec}年
- 月份編碼: {month} -> {month_dec}月
- 日期編碼: {day} -> {day_dec}日
- 狀態代碼: {status} -> {status_desc}"""

        except Exception as e:
            return f"解析錯誤: {str(e)}\n原始資料: {epc_str}"

    def handle_command_response(self, data):
        """处理命令执行响应"""
        if data[2] == 0xFF:  # 错误响应
            error_code = data[6] if len(data) > 6 else 0
            error_msg = {
                0x09: "没有找到标签",
                0x15: "写入失败",
                0x16: "访问密码不正确",
                0x17: "标签通讯错误",
                0xA3: "超出芯片容量范围"
            }.get(error_code, f"未知错误(0x{error_code:02X})")
            self.text_display.append(f"错误: {error_msg}")
        else:
            self.text_display.append("命令执行成功")

    def handle_response(self, data):
        """处理接收到的RFID响应"""
        # 连续写入模式的处理
        if self.is_multi_writing and len(data) > 3 and data[0] == 0xBB:
            if data[1] == 0x02:  # 标签读取响应
                if len(data) >= 19:
                    epc_data = data[7:19]
                    self.handle_multi_write_response(epc_data)
            elif data[1] == 0x01:  # 命令执行响应
                if data[2] == 0xFF:  # 错误响应
                    error_code = data[6] if len(data) > 6 else 0
                    error_msg = {
                        0x09: "没有找到标签",
                        0x15: "写入失败",
                        0x16: "访问密码不正确",
                        0x17: "标签通讯错误",
                        0xA3: "超出芯片容量范围"
                    }.get(error_code, f"未知错误(0x{error_code:02X})")
                    self.text_display.append(f"错误: {error_msg}")
                else:
                    self.text_display.append("写入完成，可以移除标签")
                    
        # 普通模式或批量读取模式的响应处理
        elif self.is_multi_reading:
            if len(data) > 3 and data[0] == 0xBB:
                if data[1] == 0x02:  # 标签读取响应
                    if len(data) >= 19:
                        epc_data = data[7:19]
                        epc_str = bytes_to_hex_string(epc_data)
                        
                        if epc_str not in self.processed_tags:
                            self.processed_tags.add(epc_str)
                            parsed_data = self.parse_epc_data(epc_data)
                            if parsed_data:
                                self.text_display.append(f"\n新标签：")
                                self.text_display.append(parsed_data)
                                self.text_display.append(f"当前已读取标签数：{len(self.processed_tags)}")
                                
        # 普通模式的响应处理
        else:
            hex_str = bytes_to_hex_string(data)
            self.text_display.append(f"收到数据: {hex_str}")
            
            if len(data) > 3 and data[0] == 0xBB:
                if data[1] == 0x02:  # 标签读取响应
                    if len(data) >= 19:
                        epc_data = data[7:19]
                        parsed_data = self.parse_epc_data(epc_data)
                        if parsed_data:
                            self.text_display.append("\n解析数据:")
                            self.text_display.append(parsed_data)
                            self.status_label.setText("状态：读取成功")
                elif data[1] == 0x01:  # 命令执行响应
                    self.handle_command_response(data)

    def closeEvent(self, event):
        """窗口关闭时的清理工作"""
        if self.is_multi_reading or self.is_multi_writing:
            self.stop_multi_read()
            self.stop_multi_write()
        self.rfid_reader.stop()
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
