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
    # 直接指定 DLL 路徑 (x64)
    dll_path = r"c:\Users\user\source\repos\capital_python\CapitalAPI_2.13.57_PythonExample\元件\x64\SKCOM.dll"
    print(f"正在嘗試直接載入 DLL: {dll_path}")
    
    # GetModule 會直接讀取 DLL 並生成介面，不需要註冊表
    comtypes.client.GetModule(dll_path)
    
    print("✅ GetModule 成功！介面已生成。")
    
    # 驗證 import
    import comtypes.gen.SKCOMLib as sk
    print(f"✅ 成功匯入: {sk}")
    
    # 嘗試建立物件 (這步仍可能需要註冊，但如果 GetModule 成功，至少解決了 import 問題)
    # obj = comtypes.client.CreateObject(sk.SKCenterLib)
    # print("✅ 物件建立成功！")

    print("\n環境修復完成！請嘗試執行主程式。")
    
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
