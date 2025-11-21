import comtypes.client
import sys
import os

print("="*50)
print("Capital API COM 元件初始化修復工具")
print("="*50)

# 1. 嘗試清理舊的 gen 資料夾 (如果權限允許)
try:
    import comtypes
    gen_dir = os.path.join(os.path.dirname(comtypes.__file__), 'gen')
    print(f"comtypes.gen 路徑: {gen_dir}")
    
    if os.path.exists(gen_dir):
        print("正在檢查快取...")
        # 這裡不直接刪除，避免權限問題導致崩潰，僅提示
        # print("提示: 如果初始化持續失敗，請手動刪除此資料夾內容。")
except:
    pass

print("\n正在嘗試透過 ProgID 'SKCOM.SKCenterLib' 初始化...")

try:
    # 嘗試建立 SKCenterLib 物件
    # 這會強制 comtypes 去註冊表中查找並生成 python 介面檔
    obj = comtypes.client.CreateObject("SKCOM.SKCenterLib")
    
    print("✅ SKCenterLib 物件建立成功！")
    
    # 這裡非常關鍵：CreateObject 後，comtypes 應該已經生成了 SKCOMLib
    # 我們嘗試動態載入它
    
    print("正在驗證 import...")
    import comtypes.gen.SKCOMLib as sk
    print(f"✅ 成功匯入: {sk}")
    print("\n環境修復完成！您現在可以執行主程式了。")
    
except OSError as e:
    print(f"\n❌ OSError: {e}")
    print("這通常代表 Windows 找不到該 COM 元件。")
    print("請確認：")
    print("1. 群益 API 是否已安裝？")
    print("2. 是否已執行元件註冊 (install.bat 或 regsvr32 SKCOM.dll)？")
    
except ImportError as e:
    print(f"\n❌ ImportError: {e}")
    print("物件建立成功但無法匯入模組。")
    print("請嘗試：刪除 Python 安裝目錄下的 comtypes/gen 資料夾後重試。")
    
except Exception as e:
    print(f"\n❌ 未知錯誤: {e}")
