import requests
import logging
import json
import configparser
import os
from datetime import datetime

class DiscordNotifier:
    def __init__(self, config_path='config.ini'):
        self.logger = logging.getLogger("DiscordNotifier")
        self.webhook_url = None
        self._load_config(config_path)

    def _load_config(self, config_path):
        """讀取設定檔"""
        config = configparser.ConfigParser()
        # 嘗試讀取當前目錄或上一層目錄的 config.ini
        if os.path.exists(config_path):
            config.read(config_path, encoding='utf-8')
        elif os.path.exists(os.path.join('..', config_path)):
            config.read(os.path.join('..', config_path), encoding='utf-8')
            
        if 'discord' in config and 'webhook_url' in config['discord']:
            self.webhook_url = config['discord']['webhook_url']
        else:
            self.logger.warning("Config.ini 中未找到 [discord] webhook_url 設定")

    def send(self, message: str):
        """發送訊息到 Discord"""
        if not self.webhook_url:
            return

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        payload = {
            "content": f"[{timestamp}] {message}"
        }

        try:
            response = requests.post(self.webhook_url, json=payload)
            response.raise_for_status()
        except Exception as e:
            self.logger.error(f"Discord 發送失敗: {e}")

# 測試用
if __name__ == "__main__":
    notifier = DiscordNotifier()
    notifier.send("Capital Python 測試訊息: 系統連線測試")
