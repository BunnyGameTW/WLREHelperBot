"""
模擬器設備管理器
支援多個模擬器（BlueStacks、LD Player、夜神等）
解決 BlueStacks 的特殊 ADB 連接問題
"""

import subprocess
import os
import time
import json
from typing import List, Dict, Optional
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

class EmulatorDeviceManager:
    """模擬器設備管理"""
    
    def __init__(self, adb_path: Optional[str] = None, config_path: Optional[str] = None):
        """
        初始化模擬器設備管理器
        Args:
            adb_path: ADB 路徑（None=自動查找）
            config_path: emu_paths.json 配置路徑
        """
        self.adb_path = adb_path or self._find_adb()
        self.config = self._load_config(config_path)
        self.emulator_devices = {}  # 存儲檢測到的設備信息
        self.last_update = 0
        self.update_interval = 5  # 5秒緩存

    def _find_adb(self) -> Optional[str]:
        """查找 ADB 路徑"""
        candidates = [
            os.environ.get("ANDROID_SDK_ROOT", "") + "\\platform-tools\\adb.exe",
            os.environ.get("ANDROID_HOME", "") + "\\platform-tools\\adb.exe",
            r"C:\Android\sdk\platform-tools\adb.exe",
            "adb.exe"
        ]
        
        for path in candidates:
            if path and os.path.exists(path):
                print(f"[ADB] 找到 ADB: {path}")
                return path
        
        print("[WARN] 未找到 adb.exe，請確保已安裝 Android SDK")
        return None

    def _load_config(self, config_path: Optional[str]) -> Dict:
        """加載模擬器路徑配置"""
        if config_path is None:
            config_path = "config/emu_paths.json"
        
        default_config = {
            "adb_path": self.adb_path,
            "ldplayer": {"enabled": True, "console_path": None},
            "bluestacks": {"enabled": True, "install_path": None},
            "nox": {"enabled": True, "install_path": None}
        }
        
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    return {**default_config, **config}
            except Exception as e:
                print(f"[WARN] 加載配置失敗: {e}")
        
        return default_config

    def detect_devices(self, force_refresh: bool = False) -> List[Dict]:
        """
        檢測所有連接的模擬器設備
        Returns:
            設備列表，每個設備包含 serial, name, type, port 等信息
        """
        current_time = time.time()
        
        # 使用緩存
        if not force_refresh and (current_time - self.last_update) < self.update_interval:
            return list(self.emulator_devices.values())
        
        self.emulator_devices.clear()
        devices = []
        
        # 掌握已檢測到的特定模擬器 serial -> type 映射
        known_devices = {}
        
        # 1. 優先檢測特定的模擬器 (這些檢測源更準確)
        ldplayer_devices = self._detect_ldplayer()
        for dev in ldplayer_devices:
            known_devices[dev['serial']] = 'ldplayer'
            devices.append(dev)
        
        bluestacks_devices = self._detect_bluestacks()
        for dev in bluestacks_devices:
            known_devices[dev['serial']] = 'bluestacks'
            devices.append(dev)
        
        nox_devices = self._detect_nox()
        for dev in nox_devices:
            known_devices[dev['serial']] = 'nox'
            devices.append(dev)
        
        mumu_devices = self._detect_mumu()
        for dev in mumu_devices:
            known_devices[dev['serial']] = 'mumu'
            devices.append(dev)
        
        # 2. 通過 ADB 檢測，使用已知的類型或啟發式判斷
        adb_devices = self._detect_via_adb(known_devices)
        devices.extend(adb_devices)
        
        # 存儲並返回 (避免重複)
        self.emulator_devices.clear()
        for device in devices:
            serial = device.get('serial')
            if serial and serial not in self.emulator_devices:
                self.emulator_devices[serial] = device
        
        self.last_update = current_time
        return list(self.emulator_devices.values())

    def _detect_via_adb(self, known_devices: Dict = None) -> List[Dict]:
        """通過 ADB 檢測設備
        
        Args:
            known_devices: 已由特定檢測發現的 serial -> type 映射
        """
        if known_devices is None:
            known_devices = {}
            
        devices = []
        
        if not self.adb_path or not os.path.exists(self.adb_path):
            return devices
        
        try:
            result = subprocess.run(
                [self.adb_path, "devices", "-l"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            for line in result.stdout.split('\n')[1:]:
                line = line.strip()
                if not line or line.startswith('*'):
                    continue
                
                parts = line.split()
                if len(parts) >= 2:
                    serial = parts[0]
                    status = parts[1]
                    
                    if status == "device":
                        # 檢查是否已由特定檢測發現
                        if serial in known_devices:
                            device_type = known_devices[serial]
                        else:
                            # 落後到啟發式判斷
                            device_type = self._get_emulator_type(serial, is_adb_source=True)
                        
                        # 解析設備信息
                        device_info = {
                            'serial': serial,
                            'name': self._get_device_name(serial),
                            'type': device_type,
                            'status': status,
                            'source': 'adb'
                        }
                        devices.append(device_info)
        except Exception as e:
            print(f"[WARN] ADB 檢測失敗: {e}")
        
        return devices

    def _detect_bluestacks(self) -> List[Dict]:
        """檢測 BlueStacks 模擬器"""
        devices = []
        
        if not self.config.get("bluestacks", {}).get("enabled"):
            return devices
        
        try:
            # 1. 優先使用用戶配置的路徑
            bs_paths = []
            try:
                if os.path.exists("bot_config_emu.json"):
                    with open("bot_config_emu.json", 'r', encoding='utf-8') as f:
                        bot_config = json.load(f)
                        emulator_paths = bot_config.get("emulator_paths", {})
                        if "bluestacks" in emulator_paths and emulator_paths["bluestacks"]:
                            user_bs_path = emulator_paths["bluestacks"]
                            if os.path.exists(user_bs_path):
                                bs_paths.append(user_bs_path)
                                print(f"[BLUESTACKS] 使用用戶配置路徑: {user_bs_path}")
            except Exception as e:
                print(f"[WARN] 加載用戶配置 BlueStacks 路徑失敗: {e}")
            
            # 2. 預設路徑
            bs_paths.extend([
                os.environ.get("ProgramFiles", "") + "\\BlueStacks\\",
                os.environ.get("ProgramFiles(x86)", "") + "\\BlueStacks\\",
                r"C:\Program Files\BlueStacks" + "\\",
                r"C:\Program Files (x86)\BlueStacks" + "\\",
                r"C:\Program Files\BlueStacks5" + "\\",
                r"C:\Program Files (x86)\BlueStacks5" + "\\",
            ])
            
            for bs_path in bs_paths:
                if os.path.exists(bs_path):
                    # BlueStacks 使用 adb.exe
                    bs_adb = os.path.join(bs_path, "adb.exe")
                    if os.path.exists(bs_adb):
                        # 列出 BlueStacks 實例
                        devices.extend(self._query_bluestacks_instances(bs_adb))
                    
                    # 如果找到 BlueStacks，就不再搜索其他路徑
                    if devices:
                        break
        except Exception as e:
            print(f"[WARN] BlueStacks 檢測失敗: {e}")
        
        # 方法2: 掃描 BlueStacks 使用的特定埠範圍
        if not devices:
            devices.extend(self._scan_bluestacks_ports())
        
        return devices

    def _query_bluestacks_instances(self, bs_adb: str) -> List[Dict]:
        """查詢 BlueStacks 實例"""
        devices = []
        
        try:
            # BlueStacks 使用 127.0.0.1:5555+ 的端口
            # 支援多達 10+ 個實例
            ports = list(range(5555, 5600)) + list(range(5037, 5050))  # 5555-5599 涵蓋多實例
            
            for port in ports:
                try:
                    # 嘗試連接到該端口
                    result = subprocess.run(
                        [bs_adb, "-s", f"127.0.0.1:{port}", "shell", "getprop", "ro.serialno"],
                        capture_output=True,
                        text=True,
                        timeout=1
                    )
                    
                    if result.returncode == 0 and result.stdout.strip():
                        # 找到一個活躍的實例
                        serial = f"127.0.0.1:{port}"
                        devices.append({
                            'serial': serial,
                            'name': f"BlueStacks:{port}",
                            'type': 'bluestacks',
                            'port': port,
                            'adb_path': bs_adb,
                            'status': 'device',
                            'source': 'bluestacks'
                        })
                except:
                    pass
        except Exception as e:
            print(f"[WARN] 查詢 BlueStacks 實例失敗: {e}")
        
        return devices

    def _scan_bluestacks_ports(self) -> List[Dict]:
        """掃描 BlueStacks 常用的本地 TCP 埠（並發掃描）"""
        devices = []
        
        if not self.adb_path or not os.path.exists(self.adb_path):
            return devices
        
        try:
            # BlueStacks 通常只有 1-5 個實例，使用特定埠而不是完整範圍
            # 優先掃描常見埠：5555, 5565, 5575, 5585, 5595
            # 然後是完整範圍 5555-5599
            priority_ports = [5555, 5565, 5575, 5585, 5595]
            range_ports = list(range(5555, 5600))
            
            def check_port(port):
                try:
                    result = subprocess.run(
                        [self.adb_path, "connect", f"127.0.0.1:{port}"],
                        capture_output=True,
                        text=True,
                        timeout=1
                    )
                    
                    output = result.stdout.lower() + result.stderr.lower()
                    
                    if ("connected" in output and "unable" not in output and "refused" not in output):
                        # 驗證是否確實是活躍設備
                        try:
                            verify = subprocess.run(
                                [self.adb_path, "-s", f"127.0.0.1:{port}", "shell", "getprop", "ro.product.model"],
                                capture_output=True,
                                text=True,
                                timeout=1
                            )
                            
                            if verify.returncode == 0 or (verify.stdout and verify.stdout.strip()):
                                return {
                                    'serial': f"127.0.0.1:{port}",
                                    'name': f"BlueStacks:{port}",
                                    'type': 'bluestacks',
                                    'port': port,
                                    'status': 'device',
                                    'source': 'bluestacks_scan'
                                }
                        except:
                            if "already connected" in output or "connected to" in output:
                                return {
                                    'serial': f"127.0.0.1:{port}",
                                    'name': f"BlueStacks:{port}",
                                    'type': 'bluestacks',
                                    'port': port,
                                    'status': 'device',
                                    'source': 'bluestacks_scan'
                                }
                except:
                    pass
                return None
            
            # 先用優先埠進行快速掃描
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = {executor.submit(check_port, port): port for port in priority_ports}
                for future in as_completed(futures, timeout=10):
                    result = future.result()
                    if result:
                        devices.append(result)
            
            # 如果找到足夠的 BlueStacks 實例，就不再掃描完整範圍
            if len(devices) >= 5:  # 假設最多 5 個實例
                return devices
            
            # 如果沒有找到，用完整範圍掃描（但只掃描未檢查的埠）
            remaining_ports = [p for p in range_ports if p not in priority_ports and p > max([d['port'] for d in devices], default=5555)]
            
            if remaining_ports:
                with ThreadPoolExecutor(max_workers=5) as executor:
                    futures = {executor.submit(check_port, port): port for port in remaining_ports[:20]}  # 只掃描 20 個
                    for future in as_completed(futures, timeout=15):
                        result = future.result()
                        if result:
                            devices.append(result)
                            if len(devices) >= 5:  # 找到足夠的實例就停止
                                break
        except Exception as e:
            print(f"[WARN] BlueStacks 埠掃描失敗: {e}")
        
        return devices

    def _detect_ldplayer(self) -> List[Dict]:
        """檢測 LD Player"""
        devices = []
        
        if not self.config.get("ldplayer", {}).get("enabled"):
            return devices
        
        try:
            console_path = self._find_ldplayer_console()
            if not console_path or not os.path.exists(console_path):
                # LD Player 沒有找到，但可能通過 ADB 連接
                return devices
            
            try:
                result = subprocess.run(
                    [console_path, "list2"],
                    capture_output=True,
                    text=True,
                    encoding='gbk',
                    errors='ignore',
                    timeout=3
                )
            except subprocess.TimeoutExpired:
                # 命令超時，返回空列表
                return devices
            
            for line in result.stdout.strip().split('\n'):
                if not line or ',' not in line:
                    continue
                
                parts = line.split(',')
                if len(parts) >= 2:
                    idx = parts[0].strip()
                    name = parts[1].strip()
                    
                    # LD Player 端口計算
                    try:
                        port = 5554 + int(idx) * 2
                        serial = f"emulator-{port}"
                        
                        devices.append({
                            'serial': serial,
                            'name': f"LD Player - {name}",
                            'type': 'ldplayer',
                            'port': port,
                            'index': idx,
                            'status': 'device',
                            'source': 'ldplayer'
                        })
                    except:
                        pass
        except Exception as e:
            print(f"[WARN] LD Player 檢測失敗: {e}")
        
        return devices

    def _detect_nox(self) -> List[Dict]:
        """檢測夜神模擬器（支援多實例）"""
        devices = []
        
        if not self.config.get("nox", {}).get("enabled"):
            return devices
        
        try:
            # 1. 優先使用用戶配置的路徑
            nox_adb = None
            try:
                if os.path.exists("bot_config_emu.json"):
                    with open("bot_config_emu.json", 'r', encoding='utf-8') as f:
                        bot_config = json.load(f)
                        emulator_paths = bot_config.get("emulator_paths", {})
                        if "nox" in emulator_paths and emulator_paths["nox"]:
                            user_nox_adb = os.path.join(emulator_paths["nox"], "bin", "nox_adb.exe")
                            if os.path.exists(user_nox_adb):
                                nox_adb = user_nox_adb
                                print(f"[NOX] 使用用戶配置路徑: {nox_adb}")
            except Exception as e:
                print(f"[WARN] 加載用戶配置 Nox 路徑失敗: {e}")
            
            # 2. 預設路徑
            if not nox_adb:
                nox_adb = r"C:\Nox\bin\nox_adb.exe"
                if not os.path.exists(nox_adb):
                    nox_adb = r"C:\Program Files\Nox\bin\nox_adb.exe"
                if not os.path.exists(nox_adb):
                    nox_adb = r"C:\Program Files (x86)\Nox\bin\nox_adb.exe"
            
            if os.path.exists(nox_adb):
                try:
                    result = subprocess.run(
                        [nox_adb, "devices"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    
                    for line in result.stdout.split('\n')[1:]:
                        line = line.strip()
                        if line:
                            parts = line.split()
                            if len(parts) >= 2:
                                serial = parts[0]
                                status = parts[1]
                                
                                if status == "device":
                                    devices.append({
                                        'serial': serial,
                                        'name': f"Nox - {serial}",
                                        'type': 'nox',
                                        'status': status,
                                        'source': 'nox',
                                        'adb_path': nox_adb
                                    })
                except subprocess.TimeoutExpired:
                    # Nox 檢測超時，嘗試埠掃描
                    devices.extend(self._scan_nox_ports())
            else:
                # 嘗試埠掃描 (Nox 通常在本地 TCP 埠)
                devices.extend(self._scan_nox_ports())
        except Exception as e:
            print(f"[WARN] Nox 檢測失敗: {e}")
        
        return devices
    
    def _scan_nox_ports(self) -> List[Dict]:
        """掃描 Nox 常用的埠（並發掃描）"""
        devices = []
        
        if not self.adb_path or not os.path.exists(self.adb_path):
            return devices
        
        try:
            # Nox 實例通常在 127.0.0.1:62001-62025 的埠範圍
            ports = list(range(62001, 62026))
            
            def check_port(port):
                try:
                    result = subprocess.run(
                        [self.adb_path, "connect", f"127.0.0.1:{port}"],
                        capture_output=True,
                        text=True,
                        timeout=1
                    )
                    
                    if "connected" in result.stdout.lower():
                        return {
                            'serial': f"127.0.0.1:{port}",
                            'name': f"Nox:{port}",
                            'type': 'nox',
                            'port': port,
                            'status': 'device',
                            'source': 'nox_scan'
                        }
                except:
                    pass
                return None
            
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = {executor.submit(check_port, port): port for port in ports}
                for future in as_completed(futures, timeout=10):
                    result = future.result()
                    if result:
                        devices.append(result)
        except Exception as e:
            print(f"[WARN] Nox 埠掃描失敗: {e}")
        
        return devices
    
    def _detect_mumu(self) -> List[Dict]:
        """檢測網易 MuMu 模擬器（支援多實例）"""
        devices = []
        
        if not self.config.get("mumu", {}).get("enabled", True):  # 預設啟用
            return devices
        
        try:
            # 1. 優先使用用戶配置的路徑
            mumu_console = None
            try:
                if os.path.exists("bot_config_emu.json"):
                    with open("bot_config_emu.json", 'r', encoding='utf-8') as f:
                        bot_config = json.load(f)
                        emulator_paths = bot_config.get("emulator_paths", {})
                        if "mumu" in emulator_paths and emulator_paths["mumu"]:
                            user_mumu_console = os.path.join(emulator_paths["mumu"], "emulator", "nemu-console.exe")
                            if os.path.exists(user_mumu_console):
                                mumu_console = user_mumu_console
                                print(f"[MUMU] 使用用戶配置路徑: {mumu_console}")
            except Exception as e:
                print(f"[WARN] 加載用戶配置 MuMu 路徑失敗: {e}")
            
            # 2. 預設路徑
            if not mumu_console:
                mumu_console = r"C:\Program Files\Netease\MuMu\emulator\nemu-console.exe"
                if not os.path.exists(mumu_console):
                    mumu_console = r"C:\Program Files (x86)\Netease\MuMu\emulator\nemu-console.exe"
            
            if os.path.exists(mumu_console):
                try:
                    result = subprocess.run(
                        [mumu_console, "list"],
                        capture_output=True,
                        text=True,
                        timeout=3
                    )
                    
                    for line in result.stdout.split('\n'):
                        line = line.strip()
                        if not line or ',' not in line:
                            continue
                        
                        parts = line.split(',')
                        if len(parts) >= 2:
                            try:
                                idx = parts[0].strip()
                                name = parts[1].strip()
                                
                                # MuMu 的 ADB 埠計算（通常 5555+ idx*10 或類似）
                                # 預設使用 ADB 通用端口掃描
                                devices.append({
                                    'serial': f"mumu-{idx}",
                                    'name': f"MuMu - {name}",
                                    'type': 'mumu',
                                    'index': idx,
                                    'status': 'device',
                                    'source': 'mumu',
                                    'console_path': mumu_console
                                })
                            except:
                                pass
                except subprocess.TimeoutExpired:
                    # MuMu 檢測超時
                    pass
            else:
                # 嘗試掃描 MuMu 常用埠
                devices.extend(self._scan_mumu_ports())
        except Exception as e:
            print(f"[WARN] MuMu 檢測失敗: {e}")
        
        return devices
    
    def _scan_mumu_ports(self) -> List[Dict]:
        """掃描 MuMu 常用的埠（並發掃描）"""
        devices = []
        
        if not self.adb_path or not os.path.exists(self.adb_path):
            return devices
        
        try:
            # MuMu 實例通常使用 127.0.0.1:16384+ 或本地 emulator-XXXX 格式
            ports = (
                list(range(16384, 16400)) +  # MuMu 常用範圍
                list(range(5001, 5020))      # 備用範圍
            )
            
            def check_port(port):
                try:
                    result = subprocess.run(
                        [self.adb_path, "connect", f"127.0.0.1:{port}"],
                        capture_output=True,
                        text=True,
                        timeout=1
                    )
                    
                    if "connected" in result.stdout.lower():
                        return {
                            'serial': f"127.0.0.1:{port}",
                            'name': f"MuMu:{port}",
                            'type': 'mumu',
                            'port': port,
                            'status': 'device',
                            'source': 'mumu_scan'
                        }
                except:
                    pass
                return None
            
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = {executor.submit(check_port, port): port for port in ports}
                for future in as_completed(futures, timeout=10):
                    result = future.result()
                    if result:
                        devices.append(result)
        except Exception as e:
            print(f"[WARN] MuMu 埠掃描失敗: {e}")
        
        return devices

    def _find_ldplayer_console(self) -> Optional[str]:
        """查找 LD Player 控制台"""
        # 1. 優先使用用戶配置的路徑（來自 bot_config_emu.json）
        try:
            import os.path
            if os.path.exists("bot_config_emu.json"):
                with open("bot_config_emu.json", 'r', encoding='utf-8') as f:
                    bot_config = json.load(f)
                    emulator_paths = bot_config.get("emulator_paths", {})
                    if "ldplayer" in emulator_paths and emulator_paths["ldplayer"]:
                        user_path = os.path.join(emulator_paths["ldplayer"], "dnconsole.exe")
                        if os.path.exists(user_path):
                            print(f"[LDPLAYER] 使用用戶配置路徑: {user_path}")
                            return user_path
        except Exception as e:
            print(f"[WARN] 加載用戶配置路徑失敗: {e}")
        
        # 2. 環境變量
        env_path = os.environ.get("LDPLAYER_CONSOLE", "")
        if env_path and os.path.exists(env_path):
            return env_path
        
        # 3. 預設路徑
        candidates = [
            r"C:\LDPlayer\LDPlayer9\dnconsole.exe",
            r"C:\LDPlayer\LDPlayer9\ldconsole.exe",
            r"C:\Program Files\LDPlayer\LDPlayer9\dnconsole.exe",
            r"C:\Program Files (x86)\LDPlayer\LDPlayer9\dnconsole.exe",
        ]
        
        for path in candidates:
            if path and os.path.exists(path):
                return path
        
        return None

    def _get_device_name(self, serial: str) -> str:
        """獲取設備名稱"""
        # 從設備屬性獲取
        if self.adb_path and os.path.exists(self.adb_path):
            try:
                result = subprocess.run(
                    [self.adb_path, "-s", serial, "shell", "getprop", "ro.product.model"],
                    capture_output=True,
                    text=True,
                    timeout=2
                )
                if result.returncode == 0 and result.stdout.strip():
                    return result.stdout.strip()
            except:
                pass
        
        return serial

    def _get_emulator_type(self, serial: str, is_adb_source: bool = False) -> str:
        """判斷模擬器類型
        
        Args:
            serial: 設備序列號
            is_adb_source: 是否來自 ADB 檢測源
        """
        # BlueStacks 通常使用 127.0.0.1:XXXX 格式
        if "127.0.0.1" in serial:
            # 判斷是 BlueStacks 還是 Nox/MuMu
            # Nox: 62001-62025 端口範圍
            # MuMu: 16384-16400, 5001-5020, 7555-7570 範圍
            # BlueStacks: 5555-5599 端口範圍（優先級最低）
            match = re.search(r":(\d+)$", serial)
            if match:
                port = int(match.group(1))
                if 62001 <= port <= 62025:
                    return "nox"
                elif 16384 <= port <= 16400:
                    return "mumu"
                elif 5001 <= port <= 5020 or 7555 <= port <= 7570:
                    return "mumu"
                elif 5555 <= port <= 5599:
                    return "bluestacks"
            return "unknown"
        
        # MuMu 可能使用 mumu-XXXX 格式
        if "mumu" in serial.lower():
            return "mumu"
        
        # Android Studio emulator 或其他使用 emulator-XXXX 格式
        if "emulator" in serial:
            match = re.match(r"emulator-(\d+)", serial)
            if match:
                port = int(match.group(1))
                # LD Player 明確：5554, 5556, 5558, 5560, 5562 等（僅偶數埠且 <=5600）
                if 5554 <= port <= 5600 and port % 2 == 0:
                    return "ldplayer"
                # 其他 emulator-XXXX 不判定為任何類型（可能是模擬器或未知）
            return "unknown"
        
        # 未知類型
        return "unknown"

    def get_device(self, serial: str) -> Optional[Dict]:
        """獲取單個設備信息"""
        return self.emulator_devices.get(serial)

    def get_device_count(self) -> int:
        """獲取設備數量"""
        return len(self.emulator_devices)

    def connect_adb_device(self, host: str, port: int = 5555) -> bool:
        """連接遠程 ADB 設備"""
        if not self.adb_path or not os.path.exists(self.adb_path):
            return False
        
        try:
            result = subprocess.run(
                [self.adb_path, "connect", f"{host}:{port}"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            success = "unable to connect" not in result.stdout.lower()
            if success:
                print(f"[OK] 連接 {host}:{port} 成功")
                # 刷新設備列表
                self.detect_devices(force_refresh=True)
            return success
        except Exception as e:
            print(f"[ERROR] 連接失敗: {e}")
            return False

    def save_config(self, config_path: str = "config/emu_paths.json"):
        """保存配置"""
        try:
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            print(f"[OK] 配置已保存: {config_path}")
        except Exception as e:
            print(f"[ERROR] 保存配置失敗: {e}")

    def set_adb_path(self, path: str):
        """設置 ADB 路徑"""
        if not os.path.exists(path):
            raise FileNotFoundError(f"ADB 路徑不存在: {path}")
        self.adb_path = path
        self.config["adb_path"] = path

    def set_bluestacks_path(self, path: str):
        """設置 BlueStacks 路徑"""
        if not os.path.exists(path):
            raise FileNotFoundError(f"BlueStacks 路徑不存在: {path}")
        self.config["bluestacks"]["install_path"] = path

    def set_ldplayer_console(self, path: str):
        """設置 LD Player 控制台路徑"""
        if not os.path.exists(path):
            raise FileNotFoundError(f"控制台路徑不存在: {path}")
        self.config["ldplayer"]["console_path"] = path
