using Microsoft.Extensions.Configuration; // Add this using statement
using Microsoft.Extensions.Logging; // Add this using statement
using Hangfire;
using Hangfire.Server;
using Microsoft.EntityFrameworkCore;
using Microsoft.OpenApi.Extensions;
using MySqlConnector;
using Newtonsoft.Json;
using SKCOMLib;
using StocksML.Common.Schedule;
using StocksML.Common.Utils;
using StocksML.Data;
using StocksML.Data.Entities;
using StocksML.Emum;
using StocksML.Interfase.CMS;
using StocksML.Model;
using StocksML.Model.Captial;
using StocksML.Model.Fugle;
using StocksML.Model.Line;
using StocksML.Service.CMS.Futures;
using StocksML.WebApi.Common.Utils;
using System;
using System.ComponentModel.DataAnnotations;
using System.Data;
using System.Linq;
using System.Numerics;
using System.Runtime.CompilerServices;
using static StocksML.Common.Utils.TechnicalAnalysisUtils;

namespace StocksML.Service.Captial
{
    /// <summary>
    /// 群益API背景執行
    /// </summary>
    public class APIService : BackgroundService
    {
        protected readonly IServiceScopeFactory _serviceScopeFactory;
        protected readonly IFutures _futures;
        private readonly IConfiguration _configuration; // Add this field
        private readonly ILogger<APIService> _logger; // Add this field

        private readonly SKCenterLib m_pSKCenter = new(); //登入&環境物件
        private readonly SKReplyLib m_pSKReply = new(); //回應物件
        private readonly SKOrderLib m_pSKOrder = new(); //下單物件
        private readonly SKQuoteLib m_SKQuoteLib = new(); //國內報價物件
        private readonly SKOSQuoteLib m_SKOSQuoteLib = new(); //國外報價物件
        private readonly Option _option; //共用控制項

        private static readonly Dictionary<string, List<CaptialKLine>> _kLinesByExchange = [];
        private static readonly Dictionary<string, ChartKLine> _chartKLinesByExchange = [];
        // 國內物件
        //private readonly List<CaptialKLine> _kLine; // 共用K線
        private List<CaptialKLine> _fKLine; // 期貨策略K線
        private List<CaptialKLine> _fKLineHistory; // 歷史K
        private readonly List<Data.Entities.Captial> _stockList; // 共用商品物件
        private TAKline _taKline; // 技術分析用K線
        private List<CaptialChart> _chart; // 圖表列表
        private List<ChartKLine> _chartKLine; // 圖表K線
        private int _tickIndex;
        private uint _chartId;
        // 海期物件
        //private readonly List<CaptialKLine> _kLineOS; // 共用K線
        private List<CaptialKLine> _fKLineOS; // 期貨策略K線
        private List<CaptialKLine> _fKLineHistoryOS; // 歷史K
        private readonly List<Data.Entities.Captial> _stockListOS; // 共用商品物件
        private TAKline _taKlineOS; // 技術分析用K線
        private List<CaptialChart> _chartOS; // 圖表列表
        //private List<ChartKLine> _chartKLineOS; // 圖表K線
        private int _tickIndexOS;
        private uint _chartIdOS;
        private string _OSExchange;

        // 初始化交易所的 K線儲存
        private void InitializeKLineStorage()
        {
            _kLinesByExchange["TAIFEX"] = [];
            _kLinesByExchange["NYM"] = [];
            _kLinesByExchange["CBOT"] = [];
            _kLinesByExchange["CME"] = [];
        }

        private void InitializeChartKLineStorage()
        {
            _chartKLinesByExchange["TAIFEX"] = new ChartKLine();
            _chartKLinesByExchange["NYM"] = new ChartKLine();
            _chartKLinesByExchange["CBOT"] = new ChartKLine();
            _chartKLinesByExchange["CME"] = new ChartKLine();
        }

        /// <summary>
        /// 建構子
        /// </summary>
        public APIService(IServiceScopeFactory serviceScopeFactory, IFutures futures, IConfiguration configuration, ILogger<APIService> logger)
        {
            _serviceScopeFactory = serviceScopeFactory;
            _futures = futures;
            _configuration = configuration; // Assign configuration
            _logger = logger; // Assign the injected logger

            _option = new Option
            {
                LoginID = _configuration["SKCOM:LoginID"], // Read from configuration
                LoginPwd = _configuration["SKCOM:LoginPwd"]
            };
            /*_option = new Option
            {
                LoginID = "A126208187",
                LoginPwd = "b88605105"
            };*/

            // 共用k線
            InitializeKLineStorage();
            InitializeChartKLineStorage();
            // 國內物件
            //_kLine = new List<CaptialKLine>();
            _stockList = new List<Data.Entities.Captial>();
            _fKLine = new List<CaptialKLine>();
            _fKLineHistory = new List<CaptialKLine>();
            _taKline = new TAKline();
            _chart = new List<CaptialChart>();
            _chartKLine = new List<ChartKLine>();
            _tickIndex = -1;
            _chartId = 0;
            // 海期物件
            //_kLineOS = new List<CaptialKLine>();
            _fKLineOS = new List<CaptialKLine>();
            _fKLineHistoryOS = new List<CaptialKLine>();
            _taKlineOS = new TAKline();
            _chartOS = new List<CaptialChart>();
            //_chartKLineOS = new List<ChartKLine>();
            _tickIndexOS = -1;
            _chartIdOS = 0;
            _OSExchange = "";
        }

        /// <summary>
        /// 執行
        /// </summary>
        /// <param name="stoppingToken"></param>
        /// <returns></returns>
        /// <exception cref="NotImplementedException"></exception>
        protected override async Task ExecuteAsync(CancellationToken stoppingToken)
        {
            while (!stoppingToken.IsCancellationRequested)
            {
                #region 環境設定
                // 首次執行
                if (_option.IsFirst)
                {
                    // 註冊公告事件
                    m_pSKReply.OnReplyMessage += new _ISKReplyLibEvents_OnReplyMessageEventHandler(PSKReply_OnAnnouncement);

                    // 註冊取回帳號事件
                    m_pSKOrder.OnAccount += new _ISKOrderLibEvents_OnAccountEventHandler(OrderObj_OnAccount);

                    #region 回報
                    // 回報連線結果
                    m_pSKReply.OnConnect += new _ISKReplyLibEvents_OnConnectEventHandler(m_SKReplyLib_OnConnection);

                    // 回報斷線通知
                    m_pSKReply.OnDisconnect += new _ISKReplyLibEvents_OnDisconnectEventHandler(m_SKReplyLib_OnDisconnection);

                    // 回報委託狀態
                    m_pSKReply.OnNewData += new _ISKReplyLibEvents_OnNewDataEventHandler(m_OnNewData);
                    #endregion

                    #region 國內
                    // 國內報價連線狀態事件
                    m_SKQuoteLib.OnConnection += new _ISKQuoteLibEvents_OnConnectionEventHandler(m_SKQuoteLib_OnConnection);

                    // 國內報價事件
                    m_SKQuoteLib.OnNotifyQuoteLONG += new _ISKQuoteLibEvents_OnNotifyQuoteLONGEventHandler(m_SKQuoteLib_OnNotifyQuoteLONG);

                    // 國內 Tick 回傳事件
                    m_SKQuoteLib.OnNotifyTicksLONG += new _ISKQuoteLibEvents_OnNotifyTicksLONGEventHandler(m_SKQuoteLib_OnNotifyTicks);

                    // 國內 Best5 回傳事件
                    m_SKQuoteLib.OnNotifyBest5LONG += new _ISKQuoteLibEvents_OnNotifyBest5LONGEventHandler(m_SKQuoteLib_OnNotifyBest5);

                    // 國內 可交易商品列表事件
                    m_SKQuoteLib.OnNotifyStockList += new _ISKQuoteLibEvents_OnNotifyStockListEventHandler(m_SKQuoteLib_OnNotifyStockList);

                    // 國內 歷史 Tick 回傳事件
                    m_SKQuoteLib.OnNotifyHistoryTicksLONG += new _ISKQuoteLibEvents_OnNotifyHistoryTicksLONGEventHandler(m_OnNotifyHistoryTicksLONG);

                    // 國內 歷史 K線 回傳事件
                    m_SKQuoteLib.OnNotifyKLineData += new _ISKQuoteLibEvents_OnNotifyKLineDataEventHandler(m_OnNotifyKLineData);

                    // 非同步委託 回傳事件
                    m_pSKOrder.OnAsyncOrder += new _ISKOrderLibEvents_OnAsyncOrderEventHandler(m_OnAsyncOrder);

                    
                    #endregion

                    #region 海期
                    // 海期報價連線狀態事件
                    m_SKOSQuoteLib.OnConnect += new _ISKOSQuoteLibEvents_OnConnectEventHandler(m_SKOSQuoteLib_OnConnection);
                    // 可交易商品列表
                    m_SKOSQuoteLib.OnOverseaProducts += new _ISKOSQuoteLibEvents_OnOverseaProductsEventHandler(m_SKOSQuoteLib_OnOverseaProducts);
                    // 海期 歷史 K線 回傳事件
                    m_SKOSQuoteLib.OnKLineData += new _ISKOSQuoteLibEvents_OnKLineDataEventHandler(m_SKOSQuoteLib_OnNotifyKLineDataOS);
                    // 海期 歷史 tick 回傳事件
                    m_SKOSQuoteLib.OnNotifyHistoryTicksNineDigitLONG += new _ISKOSQuoteLibEvents_OnNotifyHistoryTicksNineDigitLONGEventHandler(m_SKOSQuoteLib_OnNotifyHistoryTicksNineDigitLONG);
                    // 海期 歷史 tick 回傳事件
                    //m_SKOSQuoteLib.OnNotifyHistoryTicks += new _ISKOSQuoteLibEvents_OnNotifyHistoryTicksEventHandler(m_SKOSQuoteLib_OnNotifyHistoryTicks);
                    // 海期 即時 tick 回傳事件
                    m_SKOSQuoteLib.OnNotifyTicksNineDigitLONG += new _ISKOSQuoteLibEvents_OnNotifyTicksNineDigitLONGEventHandler(m_SKOSQuoteLib_OnNotifyTicksNineDigitLONG);
                    // 海期 即時 tick 回傳事件
                    //m_SKOSQuoteLib.OnNotifyTicks += new _ISKOSQuoteLibEvents_OnNotifyTicksEventHandler(m_SKOSQuoteLib_OnNotifyTicks);
                    
                    #endregion

                    // 使用 SGX DMA
                    //m_pSKCenter.SKCenterLib_SetAuthority(1);
                    // 海期 即時 tick 回傳事件
                    //m_pSKCenter.OnNotifySGXAPIOrderStatus += new _ISKCenterLibEvents_OnNotifySGXAPIOrderStatusEventHandler(m_OnNotifySGXAPIOrderStatus);

                    _option.IsFirst = false;
                }
                #endregion

                #region 登入
                if (!_option.IsLogin)
                {
                    // 呼叫群益帳號登入
                    _option.NCode = m_pSKCenter.SKCenterLib_Login(_option.LoginID, _option.LoginPwd);
                    GetMessage("登入", _option.NCode);
                    if (_option.NCode != 0 && _option.NCode != 2003)
                        continue;

                    // 下單物件初始化
                    _option.NCode = m_pSKOrder.SKOrderLib_Initialize();
                    GetMessage("下單物件初始化", _option.NCode);
                    if (_option.NCode != 0)
                        continue;

                    // 讀取憑證
                    _option.NCode = m_pSKOrder.ReadCertByID(_option.LoginID);
                    GetMessage("讀取憑證", _option.NCode);
                    if (_option.NCode != 0)
                        continue;

                    //取得下單帳號
                    _option.NCode = m_pSKOrder.GetUserAccount();
                    GetMessage("取得下單帳號", _option.NCode);
                    _option.IsLogin = true;
                    if (_option.NCode != 0)
                        // 取得下單帳號失敗
                        continue;

                    

                    _option.IsLogin = true;
                }
                #endregion

                #region 回報連線
                if (!_option.ReplyConnection)
                {
                    _option.NCode = m_pSKReply.SKReplyLib_ConnectByID(_option.LoginID);
                    GetMessage("回報連線", _option.NCode);
                }
                else
                {
                    int connect = m_pSKReply.SKReplyLib_IsConnectedByID(_option.LoginID);
                    _logger.LogInformation("回報連線狀態: {Connect}", connect);
                    if (connect == 0)
                    {
                        _option.NCode = m_pSKReply.SKReplyLib_ConnectByID(_option.LoginID);
                        GetMessage("回報連線", _option.NCode);
                    }
                }
                #endregion

                #region SGXAPI 回報連線
                //if (!_option.SGXAPIConnection)
                //{
                //    _option.NCode = m_pSKOrder.AddSGXAPIOrderSocket(_option.LoginID, _option.OsFutAcct);
                //    GetMessage("SGXAPI 回報連線狀態", _option.NCode);

                //    _option.NCode = m_pSKOrder.SKOrderLib_LoadOSCommodity();
                //    GetMessage("下載海期商品檔", _option.NCode);
                //}
                #endregion

                #region 國內連線

                DateTime now = DateTime.Now;
                if ((now.Hour == 14 && now.Minute == 55) || (now.Hour == 8 && now.Minute == 40))
                {
                    _logger.LogInformation("停盤重設");
                    m_SKQuoteLib.SKQuoteLib_LeaveMonitor();
                    Reset();
                }
                else
                {
                    if (!_option.Connection)
                    {
                        // 與國內報價伺服器建立連線
                        _option.NCode = m_SKQuoteLib.SKQuoteLib_EnterMonitorLONG();
                        GetMessage("與國內報價伺服器建立連線", _option.NCode);
                        if (_option.NCode != 0)
                        {
                            Reset();
                            continue;
                        }
                    }
                    else
                    {
                        // 判斷商品列表為空
                        if (_stockList.Where(w => w.Exchange == "TAIFEX").Count() == 0)
                        {
                            // 取得商品列表 0.上市 1.上櫃 2.期貨 3.選擇權
                            for (short i = 2; i <= 3; i++)
                            {
                                _option.NCode = m_SKQuoteLib.SKQuoteLib_RequestStockList(i);
                                GetMessage("取得商品列表", _option.NCode);
                                if (_option.NCode != 0)
                                {
                                    _option.NCode = m_SKQuoteLib.SKQuoteLib_EnterMonitorLONG();
                                    GetMessage("重新與國內報價伺服器建立連線", _option.NCode);
                                    continue;
                                }
                            }

                            // 回補商品列表
                            _logger.LogInformation("回補商品列表");
                            CoverStockList();
                            _logger.LogInformation("回補商品列表完成");
                        }

                        // 載入圖表
                        if (_chart.Where(w => w.CaptialExchange == "TAIFEX").Count() == 0)
                        {
                            using (var scope = _serviceScopeFactory.CreateScope())
                            {
                                var db = scope.ServiceProvider.GetRequiredService<DBContext>();
                                _chart = db.CaptialChart
                                    .Include(i => i.Captial)
                                        .ThenInclude(t => t.TradeOptions)
                                    .Include(i => i.ChartStrategies)
                                    .Where(w => w.Enable && w.CaptialExchange == "TAIFEX")
                                    .ToList();
                            }

                            short pageNo = 1;
                            foreach (var chartItem in _chart.ToList())
                            {
                                _chartId = chartItem.Id;
                                if (_chartKLine.Any(a => a.Id == chartItem.Id))
                                {
                                    // 已有載入
                                    ChartKLine tempChart = _chartKLine.Single(a => a.Id == chartItem.Id);
                                    tempChart.Option = chartItem.Captial?.TradeOptions != null ? chartItem.Captial.TradeOptions : null;
                                    tempChart.Strategy = chartItem.ChartStrategies?.Where(w => w.Enable).ToList();
                                    tempChart.ResetData();
                                }
                                else
                                {
                                    ChartKLine result = new ChartKLine
                                    {
                                        Id = chartItem.Id,
                                        Exchange = chartItem.CaptialExchange,
                                        Code = chartItem.CaptialCode,
                                        Option = chartItem.Captial?.TradeOptions,
                                        Strategy = chartItem.ChartStrategies?.Where(w => w.Enable).ToList() ?? new List<CaptialChartStrategy>()
                                    };
                                    _chartKLine.Add(result);
                                }
                                
                                // 取得期貨歷史K線
                                _option.NCode = m_SKQuoteLib.SKQuoteLib_RequestKLineAM(chartItem.CaptialCode, 0, 1, 0);
                                GetMessage("取得歷史K線", _option.NCode);
                                if (_option.NCode != 0)
                                    continue;

                                // 回補歷史K線
                                _logger.LogInformation("回補 {CaptialCode} 歷史K線", chartItem.CaptialCode);
                                CoverHistoryKLine(chartItem);
                                _logger.LogInformation("回補 {CaptialCode} 歷史K線完成", chartItem.CaptialCode);

                                // 載入歷史週期K線
                                _logger.LogInformation("載入 {CaptialCode} 週期K線", chartItem.CaptialCode);
                                LoadingChartKLine(chartItem);
                                _logger.LogInformation("載入 {CaptialCode} 週期K線 完成", chartItem.CaptialCode);

                                _logger.LogInformation("訂閱Tick");
                                try
                                {
                                    _option.NCode = m_SKQuoteLib.SKQuoteLib_RequestTicks(pageNo, chartItem.CaptialCode);
                                    pageNo++;
                                }
                                catch (Exception e)
                                {
                                    _logger.LogError(e, "訂閱Tick異常");
                                }
                            }
                        }

                    }
                }
                #endregion

                #region 海期連線
                if (!_option.OsFutConnection)
                {
                    _option.NCode = m_SKOSQuoteLib.SKOSQuoteLib_EnterMonitorLONG();
                    GetMessage("與海期報價伺服器建立連線", _option.NCode);
                    if (_option.NCode != 0)
                    {
                        OSReset();
                        continue;
                    }
                }
                else
                {
                    // 判斷商品列表為空
                    if (_stockList.Where(w => w.Exchange != "TAIFEX").Count() == 0)
                    {
                        _option.NCode = m_SKOSQuoteLib.SKOSQuoteLib_RequestOverseaProducts();
                        GetMessage("取得海期商品列表", _option.NCode);
                        if (_option.NCode != 0)
                        {
                            _option.NCode = m_SKOSQuoteLib.SKOSQuoteLib_EnterMonitorLONG();
                            GetMessage("重新與海期報價伺服器建立連線", _option.NCode);
                            continue;
                        }

                        // 回補商品列表
                        _logger.LogInformation("回補商品列表");
                        CoverStockList();
                        _logger.LogInformation("回補商品列表完成");
                    }

                    // 載入圖表
                    if (_chartOS.Where(w => w.CaptialExchange != "TAIFEX").Count() == 0)
                    {
                        using (var scope = _serviceScopeFactory.CreateScope())
                        {
                            var db = scope.ServiceProvider.GetRequiredService<DBContext>();
                            _chartOS = db.CaptialChart
                                .Include(i => i.Captial)
                                    .ThenInclude(t => t.TradeOptions)
                                .Include(i => i.ChartStrategies)
                                .Where(w => w.Enable && w.CaptialExchange != "TAIFEX")
                                .ToList();
                        }

                        short pageNo = 1;
                        foreach (var chartItem in _chartOS.ToList())
                        {
                            _chartIdOS = chartItem.Id;
                            ChartKLine result = new ChartKLine
                            {
                                Id = chartItem.Id,
                                Exchange = chartItem.CaptialExchange,
                                Code = chartItem.CaptialCode,
                                Option = chartItem.Captial?.TradeOptions,
                                Strategy = chartItem.ChartStrategies?.Where(w => w.Enable).ToList() ?? new List<CaptialChartStrategy>()
                            };
                            _chartKLine.Add(result);
                            _OSExchange = chartItem.CaptialExchange;
                            // 取得期貨歷史K線
                            _option.NCode = m_SKOSQuoteLib.SKOSQuoteLib_RequestKLine($"{chartItem.CaptialExchange},{chartItem.CaptialCode}", 0);
                            GetMessage("取得歷史K線", _option.NCode);
                            if (_option.NCode != 0)
                                continue;

                            // 回補歷史K線
                            _logger.LogInformation("回補 {CaptialCode} 歷史K線", chartItem.CaptialCode);
                            CoverHistoryKLine(chartItem);
                            _logger.LogInformation("回補 {CaptialCode} 歷史K線完成", chartItem.CaptialCode);

                            // 載入歷史週期K線
                            _logger.LogInformation("載入 {CaptialCode} 週期K線", chartItem.CaptialCode);
                            LoadingChartKLine(chartItem);
                            _logger.LogInformation("載入 {CaptialCode} 週期K線 完成", chartItem.CaptialCode);
                            
                            _logger.LogInformation("訂閱Tick");
                            try
                            {
                                _option.NCode = m_SKOSQuoteLib.SKOSQuoteLib_RequestTicks(ref pageNo, $"{chartItem.CaptialExchange},{chartItem.CaptialCode}");
                                _logger.LogInformation("訂閱Tick[{PageNo}][{Exchange}][{Code}]{NCode}", pageNo, chartItem.CaptialExchange, chartItem.CaptialCode, _option.NCode);
                                if (_option.NCode != 0)
                                {
                                    _logger.LogError("訂閱Tick 異常 {NCode}", _option.NCode);
                                }
                            }
                            catch (Exception e)
                            {
                                _logger.LogError(e, "訂閱Tick異常");
                            }
                            

                            pageNo++;
                        }
                    }
                    else
                    {
                        foreach (var chartItem in _chartOS.ToList())
                        {
                            
                            var tempKline = _chartKLine.SingleOrDefault(s => s.Id == chartItem.Id);
                            if (tempKline == null)
                            {
                                _logger.LogError("ChartKLine not found for ChartId: {ChartId}, resetting OS charts.", chartItem.Id);
                                System.Timers.Timer trmer = new System.Timers.Timer(3000)
                                {
                                    AutoReset = false,
                                };
                                trmer.Elapsed += (s, e) =>
                                {
                                    _chartOS.Clear();
                                };
                                trmer.Start();
                                continue;
                            }

                            if (tempKline.KLine1.Count != 0)
                                continue;
                            
                            

                            _chartIdOS = chartItem.Id;
                            short pageNo = -1;
                            _OSExchange = chartItem.CaptialExchange;

                            // 載入歷史週期K線
                            _logger.LogInformation("載入 {CaptialCode} 週期K線", chartItem.CaptialCode);
                            LoadingChartKLine(chartItem);
                            _logger.LogInformation("載入 {CaptialCode} 週期K線 完成", chartItem.CaptialCode);

                            _logger.LogInformation("訂閱Tick {PageNo} {Exchange},{Code}", pageNo, chartItem.CaptialExchange, chartItem.CaptialCode);
                            _option.NCode = m_SKOSQuoteLib.SKOSQuoteLib_RequestTicks(pageNo, $"{chartItem.CaptialExchange},{chartItem.CaptialCode}");
                            if (_option.NCode != 0)
                            {
                                _logger.LogError("訂閱Tick 異常 {NCode}", _option.NCode);
                                Reset();
                            }

                            pageNo++;
                        }
                    }
                }
                #endregion



                //_logger.LogInformation(now.ToString("HH:mm:ss"));
                bool isReset = false;
                //bool isResetOS = false;
                foreach (var item in _chartKLine.ToList())
                {
                    _logger.LogInformation("{Timestamp} {Code} Ticks:{TicksCount} K1:{K1Count} K5:{K5Count} K15:{K15Count} K30:{K30Count} K60:{K60Count} K2H:{K2HCount} KD:{KDCount}", DateTime.Now.ToString("MM-dd HH:mm:ss"), item.Code, item.Ticks.Count, item.KLine1.Count, item.KLine5.Count, item.KLine15.Count, item.KLine30.Count, item.KLine60.Count, item.KLine2H.Count, item.KLineD.Count);
                    /*if (item.KLine5.Count == 0 && item.Exchange == "TAIFEX")
                    {
                        _logger.LogWarning("{Code} [國內]歷史K線異常重設", item.Code);
                        m_SKQuoteLib.SKQuoteLib_LeaveMonitor();
                        isReset = true;
                    }
                    else
                    {
                        /*_logger.LogWarning("{Code} [海期]歷史K線異常重設", item.Code);
                        m_SKOSQuoteLib.SKOSQuoteLib_LeaveMonitor();
                        isResetOS = true;*/
                   // }
                }
                if (isReset) Reset();

                await Task.Delay(60000, stoppingToken);

             }
            //throw new NotImplementedException();
        }

        #region 基礎API
        /// <summary>
        /// 公告事件
        /// </summary>
        /// <param name="strUserID"></param>
        /// <param name="bstrMessage"></param>
        /// <param name="nConfirmCode"></param>
        private void PSKReply_OnAnnouncement(string strUserID, string bstrMessage, out short nConfirmCode)
        {
            _logger.LogInformation("Announcement for {UserID}: {Message}", strUserID, bstrMessage);
            nConfirmCode = -1;
        }

        /// <summary>
        /// 取得下單帳號回傳事件
        /// </summary>
        /// <param name="bstrLogInID">登入ID</param>
        /// <param name="bstrAccountData">帳號資訊。以逗點分隔每一個欄位，欄位依序為：『市場,分公司,分公司代號,帳號,身份證字號,姓名』</param>
        void OrderObj_OnAccount(string bstrLogInID, string bstrAccountData)
        {
            string[] strValues;
            strValues = bstrAccountData.Split(',');

            _logger.LogInformation("Account Info Received: {AccountData}", bstrAccountData);
            switch (strValues[0])
            {
                case "TS": // 國內證券帳號
                    _option.SecAcct = strValues[1] + strValues[3];
                    break;
                case "TF": // 國內期貨帳號
                    _option.FutAcct = strValues[1] + strValues[3];
                    break;
                case "OF": // 海外期貨帳號
                    _option.OsFutAcct = strValues[1] + strValues[3];
                    break;
            }
        }

        /// <summary>
        /// 解析訊息代碼
        /// </summary>
        /// <param name="strType">執行類型</param>
        /// <param name="nCode">待解析代碼</param>
        /// <returns></returns>
        private void GetMessage(string strType, int nCode)
        {
            string strInfo = "";

            // 取得最後一筆LOG
            if (nCode != 0)
                strInfo = "【" + m_pSKCenter.SKCenterLib_GetLastLogInfo() + "】";
            try
            {
                string message = nCode.ToString() + "【" + strType + "】【" + m_pSKCenter.SKCenterLib_GetReturnCodeMessage(nCode) + "】" + strInfo;
                _logger.LogInformation(message);
            }catch (Exception e)
            {
                _logger.LogError(e, "Error in GetMessage for Type: {strType}, Code: {nCode}", strType, nCode);
            }
            
        }

        /// <summary>
        /// SGX API DMA專線下單連線狀態。
        /// </summary>
        /// <param name="nStatus">回傳連線狀態(3002 、3026 、1053)</param>
        /// <param name="bstrOFAccount">回傳已登入成功之海期帳號。</param>
        void m_OnNotifySGXAPIOrderStatus(int nStatus, string bstrOFAccount)
        {
            string status;
            _option.NCode = nStatus;
            if (nStatus == 3026)
            {
                status = "成功";
                _option.SGXAPIConnection = true;
            }
            else
            {
                status = "失敗";
                _option.SGXAPIConnection = false;
            }
                
            _logger.LogInformation("[SGX API DMA專線下單連線狀態][{OFAccount}][{Status}]", bstrOFAccount, status);
        }
        #endregion

        #region 下單API
        /// <summary>
        /// 回傳非同步委託結果
        /// </summary>
        /// <param name="nThreadID">交易ID</param>
        /// <param name="nCode">收單結果代碼</param>
        /// <param name="bstrMessage">收單回傳訊息 成功:委託序號 失敗:失敗原因</param>
        void m_OnAsyncOrder(int nThreadID, int nCode, string bstrMessage)
        {
            _logger.LogInformation("非同步委託結果 [交易ID:{ThreadID}] [代碼:{Code}] [訊息:{Message}]", nThreadID, nCode, bstrMessage);
        }
        #endregion

        #region 回報
        /// <summary>
        /// 接收連線結果
        /// </summary>
        /// <param name="bstrUserID">登入ID</param>
        /// <param name="nErrorCode">表錯誤待馬</param>
        private void m_SKReplyLib_OnConnection(string bstrUserID, int nErrorCode)
        {
            _logger.LogInformation("[回報連線結果][{UserID}][{ErrorCode}]", bstrUserID, nErrorCode);
            System.Timers.Timer trmer = new System.Timers.Timer(3000)
            {
                AutoReset = false,
            };
            trmer.Elapsed += (s, e) =>
            {
                _option.ReplyConnection = nErrorCode == 0;
            };
            trmer.Start();
        }

        /// <summary>
        /// 接收斷線通知
        /// </summary>
        /// <param name="bstrUserID">登入ID</param>
        /// <param name="nErrorCode">表錯誤待馬</param>
        private void m_SKReplyLib_OnDisconnection(string bstrUserID, int nErrorCode)
        {
            _logger.LogWarning("[回報斷線][{UserID}][{ErrorCode}]", bstrUserID, nErrorCode);
            System.Timers.Timer trmer = new System.Timers.Timer(3000)
            {
                AutoReset = false,
            };
            trmer.Elapsed += (s, e) =>
            {
                _option.ReplyConnection = false;
            };
            trmer.Start();
        }

        /// <summary>
        /// 委託回報
        /// </summary>
        /// <param name="bstrUserID">登入ID</param>
        /// <param name="BstrData">回傳資料以,分隔</param>
        void m_OnNewData(string bstrUserID, string BstrData)
        {
            _logger.LogInformation("委託回報 {UserID} {Data}", bstrUserID, BstrData);

            // 將成交的結果回寫到History
            string[] data = BstrData.Split(",");
            string KeyNo = data[0]; // 委託序號
            string MarketType = data[1]; // 市場別 TS:證券 TA:盤後 TL:零股 TP:興櫃 TC: 盤中零股 TF:期貨 TO:選擇權 OF:海期OO: 海選 OS:複委託
            string Type = data[2]; // 回報狀態 N:委託 C:取消 U:改量 P:改價 D:成交 B:改價改量S:動態退單
            string OrderErr = data[3]; // 錯誤碼 Y:失敗 T:逾時 N:正常
            string Broker = data[4]; // TS,TA,TL,TP: 分公司代號 unit no TF,TO: IB 代號 broker id
            string CustNo = data[5]; // 交易帳號
            string BuySell = data[6]; // 委託設定
            string ExchangeID = data[7]; // 交易所
            string ComId = data[8]; // 商品代碼
            string StrikePrice = data[9]; // 履約價 七位整數
            string OrderNo = data[10]; // 委託書號
            string Price = data[11]; // 價格,代表已經處理的價格 其餘為根據 Type 種類不同 N:「委託」為委託價；D:「成交」為成交價
            string Numerator = data[12]; // 海外期貨回報用，分子
            string Denominator = data[13]; // 海外期貨回報用，分母
            string Price1 = data[14]; // 海外期貨回報用，觸發價格  國內期選成交時，第一腳成交價
            string Numerator1 = data[15]; // 海外期貨回報用，第一腳觸發價格分子 
            string Denominator1 = data[16]; // 海外期貨回報用，觸發價格分母
            string Price2 = data[17]; // 國內期選成交時，第二腳成交價
            string Numerator2 = data[18]; // 第二腳觸發價格分子
            string Denominator2 = data[19]; // 第二腳觸發價格分母
            string Qty = data[20]; // TS TC OS股數 TF TO OF OO口數 根據 Type 種類 N:「委託」為委託量，D:「成交」為成交量 U:「改量」為減量數，C:「刪單」為原委託剩量
            string BeforeQty = data[21]; // (僅提供證券、複委託市場)參考欄位，異動變更前量，刪單為空值
            string AfterQty = data[22]; // (僅提供證券、複委託市場)參考欄位，異動變更後量，刪單為空值 
            string Date = data[23]; // 交易日期
            string Time = data[24]; // 交易時間(含冒號EX: 01:02:03)
            string OkSeq = data[25]; // 成交序號(請以ExecutionNo為主)
            string SubID = data[26]; // 子帳帳號
            string SaleNo = data[27]; // 營業員編號
            string Agent = data[28]; // 委託介面
            string TradeDate = data[29]; // 委託日期(僅提供海外委託，國內尚未提供)
            string MsgNo = data[30]; // 回報流水號
            string PreOrder = data[31]; // A:盤中單 B:預約單(僅國內期、選委託)
            string ComId1 = data[32]; // 第一腳商品代碼
            string YearMonth1 = data[33]; // 第一腳商品結算年月
            string StrikePrice1 = data[34]; // 第一腳商品履約價
            string ComId2 = data[35]; // 第二腳商品代碼
            string YearMonth2 = data[36]; // 第二腳商品結算年月
            string StrikePrice2 = data[37]; // 第二腳商品履約價
            string ExecutionNo = data[38]; // 成交序號
            string PriceSymbol = data[39]; // 下單期標
            string Reserved = data[40]; // (僅國內期、選委託)盤別A：T盤  B：T+1盤 
            string OrderEffective = data[41]; // 有效委託日
            string CallPut = data[42]; // 選擇權類型C：Call　P：Put
            string OrderSeq = data[43]; // (僅海期選)交易所單號，依海外交易所實際提供為主，又稱上手單號
            string ErrorMsg = data[44]; // 當第四欄位OrderErr為Y時，委託單錯誤訊息
            string CancelOrderMarkByExchange = data[45]; // 交易所動態退單代碼 E: 交易所動態退單
            string ExchangeTandemMsg = data[46]; // 交易所或後台退單訊息 [00]:2碼數字,交易所回應代碼及訊息; [000]:3碼數字,交易後台代碼及訊息; [D] 委託成功後,由交易所主動退單及退單原因
            string SeqNo = data[47]; // 13碼序號(成交單含IOC/FOK產生取消單)
            //string OFSTPFlag = data[48]; // [海期][停損限價/停損市價][已觸發] [委託回報] 海期停損單觸發註記: Y

            if (Type == "D")
            {
                Task.Delay(500).GetAwaiter().GetResult();
      
                using (var scope = _serviceScopeFactory.CreateScope())
                {
                    var db = scope.ServiceProvider.GetRequiredService<DBContext>();
                    var history = db.CaptialTradeHistory.SingleOrDefault(s => s.OrderNo == SeqNo);
                    if (history == null)
                    {
                        _logger.LogError("成交回報異常，DB查無該交易!! OrderNo: {SeqNo}", SeqNo);
                        return;
                    }
                    history.Price = Convert.ToSingle(Price);
                    history.IsDeal = true;
                    db.CaptialTradeHistory.Update(history);
                    db.SaveChanges();
                }
            }
        }
        #endregion

        #region 國內報價 API及監聽
        /// <summary>
        /// 回傳技術分析資訊
        /// </summary>
        /// <param name="bstrStockNo">股票代碼</param>
        /// <param name="bstrData">資料 目前皆使用新版1分線</param>
        void m_OnNotifyKLineData(string bstrStockNo, string bstrData)
        {
            var temp = bstrData.Split(",");
            DateTime date;
            if (temp[0].Length == 10)
                DateTime.TryParseExact(temp[0], "yyyy/MM/dd", null, System.Globalization.DateTimeStyles.None, out date);
            else
                DateTime.TryParseExact(temp[0], "yyyy/MM/dd HH:mm", null, System.Globalization.DateTimeStyles.None, out date);

            _kLinesByExchange["TAIFEX"].Add(new CaptialKLine
            {
                Code = bstrStockNo,
                Exchange = "TAIFEX",
                Date = date,
                Open = Convert.ToSingle(temp[1]),
                High = Convert.ToSingle(temp[2]),
                Low = Convert.ToSingle(temp[3]),
                Close = Convert.ToSingle(temp[4]),
                Volume = Convert.ToInt32(temp[5])
            });
        }

        /// <summary>
        /// 歷史Tick 回傳
        /// </summary>
        /// <param name="sMarketNo">報價有異動的商品市場別</param>
        /// <param name="nIndex">系統所編的索引代碼</param>
        /// <param name="nPtr">表示資料的位址(Key)</param>
        /// <param name="nDate">交易日期。(YYYYMMDD)</param>
        /// <param name="nTimehms">時間1。(時：分：秒’毫秒"微秒)</param>
        /// <param name="nTimemillismicros">時間2。(’毫秒"微秒)</param>
        /// <param name="nBid">買價</param>
        /// <param name="nAsk">賣價</param>
        /// <param name="nClose">成交價</param>
        /// <param name="nQty">成交量</param>
        /// <param name="nSimulate">0:一般揭示 1:試算揭示</param>
        void m_OnNotifyHistoryTicksLONG(short sMarketNo, int nIndex, int nPtr, int nDate, int nTimehms, int nTimemillismicros, int nBid, int nAsk, int nClose, int nQty, int nSimulate)
        {
            TickLine tick = new TickLine
            {
                SMarketNo = sMarketNo,
                NIndex = nIndex,
                NPtr = nPtr,
                NDate = nDate,
                NTimehms = nTimehms,
                NTimemillismicros = nTimemillismicros,
                NBid = nBid,
                NAsk = nAsk,
                NClose = nClose / 100,
                NQty = nQty,
                NSimulate = nSimulate
            };

            ChartKLine tempChart;
            if (_tickIndex != nIndex)
            {
                // 判斷tick所屬chart
                tempChart = _chartKLine.FirstOrDefault(a => a.SIndex == -1 && a.Exchange == "TAIFEX");
                if (tempChart == null)
                {
                    // _logger.LogWarning("[m_OnNotifyHistoryTicksLONG] No available chart found for new tick.");
                    return;
                }
                tempChart.SIndex = nIndex;
                _tickIndex = nIndex;
                
            }
            else
            {
                tempChart = _chartKLine.SingleOrDefault(a => a.SIndex == nIndex && a.Exchange == "TAIFEX");
                if (tempChart == null)
                {
                    // _logger.LogWarning("[m_OnNotifyHistoryTicksLONG] No matching chart found for index {nIndex}", nIndex);
                    return;
                }
            }

            if (nClose != 0)
            {
                for(sbyte cycle = 1; cycle <= 5; cycle++)
                {
                    tempChart.AddHistoryTick(tick, cycle);
                }
            }


            //_tickLine.Add(tick);
            //AddTickToFKline(tick);
            /*featureTXTicks.Add(new FeatureTxTick
            {
                Ptr = (uint)nPtr,
                Date = (uint)nDate,
                Timehms = (uint)nTimehms,
                Timemillismicros = (uint)nTimemillismicros,
                Bid = (uint)nBid,
                Ask = (uint)nAsk,
                Close = (uint)nClose,
                Qty = (uint)nQty
            });*/
        }

        /// <summary>
        /// 國內 Best5 回傳事件
        /// </summary>
        void m_SKQuoteLib_OnNotifyBest5(short sMarketNo, int nStockIdx, int nBestBid1, int nBestBidQty1, int nBestBid2, int nBestBidQty2, int nBestBid3, int nBestBidQty3, int nBestBid4, int nBestBidQty4, int nBestBid5, int nBestBidQty5, int nExtendBid, int nExtendBidQty, int nBestAsk1, int nBestAskQty1, int nBestAsk2, int nBestAskQty2, int nBestAsk3, int nBestAskQty3, int nBestAsk4, int nBestAskQty4, int nBestAsk5, int nBestAskQty5, int nExtendAsk, int nExtendAskQty, int nSimulate)
        {
            float dDigitNum = 100;

            Best5 best5 = new Best5
            {
                nBestAsk1 = nBestAsk1 / dDigitNum,
                nBestAsk2 = nBestAsk2 / dDigitNum,
                nBestAsk3 = nBestAsk3 / dDigitNum,
                nBestAsk4 = nBestAsk4 / dDigitNum,
                nBestAsk5 = nBestAsk5 / dDigitNum,
                nBestAskQty1 = nBestAskQty1,
                nBestAskQty2 = nBestAskQty2,
                nBestAskQty3 = nBestAskQty3,
                nBestAskQty4 = nBestAskQty4,
                nBestAskQty5 = nBestAskQty5,
                nBestBid1 = nBestBid1 / dDigitNum,
                nBestBid2 = nBestBid2 / dDigitNum,
                nBestBid3 = nBestBid3 / dDigitNum,
                nBestBid4 = nBestBid4 / dDigitNum,
                nBestBid5 = nBestBid5 / dDigitNum,
                nBestBidQty1 = nBestBidQty1,
                nBestBidQty2 = nBestBidQty2,
                nBestBidQty3 = nBestBidQty3,
                nBestBidQty4 = nBestBidQty4,
                nBestBidQty5 = nBestBidQty5,
                nExtendAsk = nExtendAsk / dDigitNum,
                nExtendAskQty = nExtendAskQty,
                nExtendBid = nExtendBid / dDigitNum,
                nExtendBidQty = nExtendBidQty,
                nSimulate = nSimulate,
            };

            var tempChart = _chartKLine.SingleOrDefault(a => a.SIndex == nStockIdx);
            if (tempChart == null)
            {
                // _logger.LogWarning("[m_SKQuoteLib_OnNotifyBest5] No matching chart found for index {nStockIdx}", nStockIdx);
                return;
            }
            tempChart.Best5 = best5;
        }

        /// <summary>
        /// 即時Tick 回傳
        /// </summary>
        /// <param name="sMarketNo"></param>
        /// <param name="nStockIdx"></param>
        /// <param name="nPtr"></param>
        /// <param name="nDate"></param>
        /// <param name="nTimehms"></param>
        /// <param name="nTimemillismicros"></param>
        /// <param name="nBid"></param>
        /// <param name="nAsk"></param>
        /// <param name="nClose"></param>
        /// <param name="nQty"></param>
        /// <param name="nSimulate"></param>
        private void m_SKQuoteLib_OnNotifyTicks(short sMarketNo, int nStockIdx, int nPtr, int nDate, int nTimehms, int nTimemillismicros, int nBid, int nAsk, int nClose, int nQty, int nSimulate)
        {
            try
            {
                TickLine tick = new TickLine
                {
                    SMarketNo = sMarketNo,
                    NIndex = nStockIdx,
                    NPtr = nPtr,
                    NDate = nDate,
                    NTimehms = nTimehms,
                    NTimemillismicros = nTimemillismicros,
                    NBid = nBid,
                    NAsk = nAsk,
                    NClose = nClose / 100F,
                    NQty = nQty,
                    NSimulate = nSimulate
                };

                var tempChart = _chartKLine.SingleOrDefault(a => a.SIndex == nStockIdx && a.Exchange == "TAIFEX");
                if (tempChart == null)
                {
                    // _logger.LogWarning("[m_SKQuoteLib_OnNotifyTicks] No matching chart found for index {nStockIdx}", nStockIdx);
                    return;
                }
                if (nClose != 0)
                {
                    for (sbyte cycle = 1; cycle <= 5; cycle++)
                    {
                        BaseKLine temp;
                        switch (cycle)
                        {
                            case 1: temp = tempChart.KLine1.SkipLast(1).Last(); break;
                            case 2: temp = tempChart.KLine5.SkipLast(1).Last(); break;
                            case 3: temp = tempChart.KLine15.SkipLast(1).Last(); break;
                            case 4: temp = tempChart.KLine30.SkipLast(1).Last(); break;
                            case 5: temp = tempChart.KLine60.SkipLast(1).Last(); break;
                            //case 6: temp = tempChart.KLineD.Last(); break;
                            case 9: temp = tempChart.KLine2H.SkipLast(1).Last(); break;
                            default: continue;
                        }
                         
                        // 更新K線並判斷是否為新K
                        bool isNewBar = tempChart.AddNotifyTick(tick, cycle);

                        // 不論是否為新K棒，都進行策略判斷 (實現即時停損)
                        if (tempChart.Option != null)
                        {
                            if (isNewBar)
                            {
                                _logger.LogInformation("新增K線{Code} {Cycle} {Date} {Open} {Close}", tempChart.Code, cycle, temp.Date, temp.Open, temp.Close);
                                // 特定情況通知 (可保留或按需修改)
                                if (cycle == 2 && tempChart.KLine5.SkipLast(1).Last().High >= tempChart.KLine5.SkipLast(1).Last().BBUB)
                                {
                                    SendLineMsg($"[台指近][5分][布林通道][上緣]觸價通知");
                                }
                                else if (cycle == 2 && tempChart.KLine5.SkipLast(1).Last().Low <= tempChart.KLine5.SkipLast(1).Last().BBLB)
                                {
                                    SendLineMsg($"[台指近][5分][布林通道][下緣]觸價通知");
                                }
                            }

                            // 判斷有相同週期策略
                            if (tempChart.Strategy != null && tempChart.Strategy.Any(a => a.Cycle == cycle))
                            {
                                var stratehys = tempChart.Strategy.Where(a => a.Cycle == cycle);
                                // 迴圈策略
                                foreach (var strategy in stratehys)
                                {
                                    // 取得最後一筆交易
                                    List<CaptialTradeHistory> historys;
                                    using (var scope = _serviceScopeFactory.CreateScope())
                                    {
                                        var db = scope.ServiceProvider.GetRequiredService<DBContext>();
                                        if (tempChart.Option.IsFake)
                                            historys = db.CaptialTradeHistory.Where(w => w.ChartId == tempChart.Id && w.IsFake && !w.IsDeal && w.StrategyId == strategy.Id).ToList();
                                        else
                                            historys = db.CaptialTradeHistory.Where(w => w.ChartId == tempChart.Id && !w.IsFake && w.IsDeal && w.StrategyId == strategy.Id).ToList();
                                    }

                                    var groups = historys.GroupBy(g => g.TradeId).ToList();
                                    var history = groups.LastOrDefault(w => w.Count() == 1);
                                    if (history != null)
                                    {
                                        var tempHistory = history.First();
                                        var result = _futures.PublicStrategy(tempChart, tempHistory, tempHistory.TradeId, strategy.Cycle, strategy.Strategy, !isNewBar);
                                        if (result != SignalType.Non)
                                        {
                                            _logger.LogInformation("[{Code}]result {Result}", tempChart.Code, result);
                                            SeanOrder(result, tempChart, tempHistory, tempHistory.TradeId, strategy);
                                        }
                                    }
                                    else if (isNewBar) // 只在新K棒時判斷進場
                                    {
                                        uint maxId;
                                        using (var scope = _serviceScopeFactory.CreateScope())
                                        {
                                            var db = scope.ServiceProvider.GetRequiredService<DBContext>();
                                            maxId = db.CaptialTradeHistory.Any(w => w.ChartId == tempChart.Id) ? db.CaptialTradeHistory.Where(w => w.ChartId == tempChart.Id).Max(m => m.TradeId) : 0;
                                        }
                                        var result = _futures.PublicStrategy(tempChart, null, maxId, strategy.Cycle, strategy.Strategy, false);
                                        if (result != SignalType.Non)
                                        {
                                            _logger.LogInformation("[{Code}]result {Result}", tempChart.Code, result);
                                            SeanOrder(result, tempChart, null, maxId, strategy);
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "[OnNotifyTicks] Error");
            }
        }

        /// <summary>
        /// 國內報價回應事件
        /// </summary>
        /// <param name="sMarketNo"></param>
        /// <param name="nStockIdx"></param>
        void m_SKQuoteLib_OnNotifyQuoteLONG(short sMarketNo, int nStockIdx)
        {
            // 報價資訊物件
            SKSTOCKLONG pSKStockLONG = new SKSTOCKLONG();

            // 取得最新報價寫入報價資訊物件
            m_SKQuoteLib.SKQuoteLib_GetStockByIndexLONG(sMarketNo, nStockIdx, ref pSKStockLONG);

            // 將報價資訊物件輸出在 DataGridView
            //onUpdateQuote(pSKStockLONG);
        }

        /// <summary>
        /// 商品列表 回傳
        /// </summary>
        /// <param name="sMarketNo">市場別代號</param>
        /// <param name="bstrStockData">以「,」分隔每一欄，欄位依序為：[商品代碼],[商名名稱],[最後交易日],[交易所商品代碼]</param>
        private void m_SKQuoteLib_OnNotifyStockList(short sMarketNo, string bstrStockData)
        {
            //_logger.LogInformation("商品列表回傳" + bstrStockData);
            var temp = bstrStockData.Split(";");
            foreach (var item in temp)
            {
                if (string.IsNullOrEmpty(item))
                    continue;
                var stock = item.Split(",");
                if (DateTime.TryParseExact(stock[2], "yyyyMMdd", null, System.Globalization.DateTimeStyles.None,out DateTime lastTradeDay))
                {
                    _stockList.Add(new Data.Entities.Captial()
                    {
                        Exchange = "TAIFEX",
                        Code = stock[0],
                        Name = stock[1],
                        LastTradeDay = lastTradeDay,
                        OrderID = stock[3],
                        MarketNo = sMarketNo
                    });
                }
            }

            /*txtMessage.AppendText(sMarketNo + "\n");
            txtMessage.AppendText(bstrStockData + "\n");*/
        }

        /// <summary>
        /// 接收連線狀態
        /// </summary>
        /// <param name="nKind">狀態碼</param>
        /// <param name="nCode">表示事件所獲得的代碼，代碼為0值即表示執行正確，非0表示例外事件。</param>
        private void m_SKQuoteLib_OnConnection(int nKind, int nCode)
        {
            GetMessage("國內連線", nCode);
            switch (nKind)
            {
                // 連線中斷
                case 3002:
                    _option.Connection = false;
                    break;
                // 網路斷線
                case 3021:
                    _option.Connection = false;
                    break;
                // 報價商品載入完成
                case 3003:
                case 3001:
                case 0:
                    _option.Connection = true;
                    break;
            }
            Reset();
        }

        /// <summary>
        /// 回補商品列表
        /// </summary>
        private void CoverStockList()
        {
            using (var scope = _serviceScopeFactory.CreateScope())
            {
                var db = scope.ServiceProvider.GetRequiredService<DBContext>();
                if (db.Captial.Any())
                {
                    var stocks = new List<Data.Entities.Captial>();
                    List<Data.Entities.Captial> codeList = db.Captial.Where(w => true).ToList();
                    // 新增
                    stocks = _stockList.Where(w => !codeList.Any(a => a.Code == w.Code && a.Exchange == w.Exchange)).ToList();

                    db.Captial.AddRange(stocks);
                    db.SaveChanges();
                    // 更新
                    stocks = stocks.Where(w => _stockList.Any(a => a.Code == w.Code && a.Exchange == w.Exchange)).ToList();
                    foreach (var stock in stocks)
                    {
                        var temp = _stockList.Single(s => s.Code == stock.Code && s.Exchange == stock.Exchange);
                        stock.LastTradeDay = temp.LastTradeDay;
                        stock.OrderID = temp.OrderID;
                        stock.Name = temp.Name;
                    }
                    db.Captial.UpdateRange(stocks);
                    db.SaveChanges();
                }
                else
                {
                    db.Captial.AddRange(_stockList);
                    db.SaveChanges();
                }
            }
        }

        /// <summary>
        /// 回補歷史K線
        /// </summary>
        private void CoverHistoryKLine(CaptialChart chart)
        {
            string featureCode = chart.CaptialCode;
            string featureExchange = chart.CaptialExchange;
            var addKlines = new List<CaptialKLine>();

            using (var scope = _serviceScopeFactory.CreateScope())
            {
                var db = scope.ServiceProvider.GetRequiredService<DBContext>();

                #region 期貨
                #region 基礎分K
                if (db.CaptialKLine.Any(a => a.Code == featureCode && a.Exchange == featureExchange))
                {
                    var lastKLineDate = db.CaptialKLine.Where(w => w.Code == featureCode && w.Exchange == featureExchange).OrderBy(w => w.Date).Last().Date;
                    addKlines = _kLinesByExchange[featureExchange].Where(w => w.Code == featureCode && w.Date > lastKLineDate).ToList();
                }
                else
                {
                    addKlines = _kLinesByExchange[featureExchange].Where(w => w.Code == featureCode).ToList();
                }

                db.CaptialKLine.AddRange(addKlines);
                db.SaveChanges();
                #endregion

                #region 週期K線
                for (sbyte cycle = 9; cycle >= 1; cycle--)
                {
                    IQueryable<CaptialKLine> tempKline;
                    int count;
                    // 從空新增
                    if (!db.CaptialKLineCycle.Any(a => a.Code == featureCode && a.Exchange == featureExchange && a.Cycle == cycle))
                        tempKline = db.CaptialKLine.Where(w => w.Code == featureCode && w.Exchange == featureExchange);
                    // 更新現有
                    else
                    {
                        var lastDate = db.CaptialKLineCycle.OrderBy(o => o.Date).Last(a => a.Code == featureCode && a.Exchange == featureExchange && a.Cycle == cycle).Date;
                        tempKline = db.CaptialKLine.Where(w => w.Code == featureCode && w.Exchange == featureExchange && w.Date >= lastDate);
                    }

                    count = tempKline.Count();
                    _fKLineHistory = new List<CaptialKLine>();
                    for (int i = 0; i < count; i += 10000)
                    {
                        _logger.LogInformation("[{FeatureCode}][{FeatureExchange}][{Cycle}]載入歷史分K {i} / {count}", featureCode, featureExchange, cycle, i, count);
                        _fKLineHistory.AddRange(tempKline.Skip(i).Take(10000));
                    }
                    SetCycleKLine(cycle, _fKLineHistory);
                }
                #endregion
                int cycleCount = db.CaptialKLineCycle.Where(a => a.Code == featureCode && a.Exchange == featureExchange && a.Cycle == 5).Count();

                _fKLine = db.CaptialKLineCycle.Where(a => a.Code == featureCode && a.Exchange == featureExchange && a.Cycle == 5).OrderBy(o => o.Date).Skip(cycleCount > 1000 ? cycleCount - 1000 : 0).Select(s => new CaptialKLine
                {
                    Exchange = s.Exchange,
                    Code = s.Code,
                    Open = s.Open,
                    High = s.High,
                    Low = s.Low,
                    Close = s.Close,
                    Date = s.Date,
                    Volume = s.Volume
                }).ToList();

                #endregion
            }
        }

        /// <summary>
        /// 回補技術分析
        /// </summary>
        private void CoverTechnicalAnalysis()
        {
            using (var scope = _serviceScopeFactory.CreateScope())
            {
                var db = scope.ServiceProvider.GetRequiredService<DBContext>();
                // 取得有未技術分析之股票
                // 以Pma5為基準
                var stockCode = db.Stocks.Select(s => s.Code).ToList();

                foreach (var stock in stockCode)
                {
                    if (db.StocksKLine.Any(a => a.StockCode == stock && a.PMa5 == 0))
                    {
                        List<StocksKLine> oldKLines = db.StocksKLine.Where(w => w.StockCode == stock).OrderBy(o => o.Date).ToList();
                        List<StocksKLine> updateKLines = new List<StocksKLine>();
                        List<StocksKLine> tempKLines = new List<StocksKLine>();
                        for (int i = 0; i < oldKLines.Count; i++)
                        {
                            if (oldKLines[i].PMa5 != 0)
                                continue;

                            #region 均線
                            var dataKLines = oldKLines.Where(w => w.Date <= oldKLines[i].Date).OrderByDescending(o => o.Date).Take(60).ToList();

                            tempKLines = dataKLines.Take(10).ToList();
                            oldKLines[i].PMa10 = tempKLines.Select(s => s.Close).Average();
                            oldKLines[i].VMa10 = (float)tempKLines.Select(s => s.Volume).Average();

                            tempKLines = dataKLines.Take(20).ToList();
                            oldKLines[i].PMa20 = tempKLines.Select(s => s.Close).Average();

                            oldKLines[i].PMa60 = dataKLines.Select(s => s.Close).Average();
                            #endregion

                            #region 漲跌
                            if (dataKLines.Count() > 1)
                            {
                                oldKLines[i].Change = oldKLines[i].Close - oldKLines[i - 1].Close;
                                oldKLines[i].ChangeRate = ((oldKLines[i].Close / oldKLines[i - 1].Close) - 1) * 100;
                            }
                            #endregion

                            #region KD
                            float previousK9 = 0, previousD9 = 0;
                            if (dataKLines.Count() > 1)
                            {
                                previousK9 = oldKLines[i - 1].K9;
                                previousD9 = oldKLines[i - 1].D9;
                            }

                            KDCalculatorM kd = TechnicalAnalysisUtils.KDCalculator(
                                dataKLines.Take(9).Select(s => s.High).ToList(),
                                dataKLines.Take(9).Select(s => s.Low).ToList(),
                                dataKLines.Take(9).Select(s => s.Close).ToList(),
                                previousK9, previousD9);

                            oldKLines[i].K9 = kd.K;
                            oldKLines[i].D9 = kd.D;
                            #endregion

                            #region 布林通道
                            //BollingerBandsM bb = TechnicalAnalysisUtils.BollingerBands();
                            #endregion

                            #region MACD

                            #endregion

                            updateKLines.Add(oldKLines[i]);
                        }

                        db.StocksKLine.UpdateRange(updateKLines);
                        db.SaveChanges();
                    }
                }
            }
        }

        private void Reset()
        {

            if (_stockList.Count > 0)
            {
                _logger.LogWarning("[國內重置]");
                _stockList.Clear();
                _chart.Clear();
                _chartKLine.Clear();
                _fKLine.Clear();
                _tickIndex = -1;
                _chartId = 0;
                _kLinesByExchange["TAIFEX"].Clear();
                _kLinesByExchange["NYM"].Clear();
                _kLinesByExchange["CBOT"].Clear();
                _kLinesByExchange["CME"].Clear();
                //_option.OsFutConnection = false;
                //m_SKOSQuoteLib.SKOSQuoteLib_Initialize();
                //m_SKOSQuoteLib.SKOSQuoteLib_LeaveMonitor();
                //_chartOS.Clear();
                _tickIndexOS = -1;
                _chartIdOS = 0;
                _OSExchange = "";
            }
        }
        #endregion

        #region 海期報價


        /// <summary>
        /// 接收連線狀態
        /// </summary>
        /// <param name="nKind"></param>
        /// <param name="nCode"></param>
        private void m_SKOSQuoteLib_OnConnection(int nKind, int nCode)
        {
            GetMessage("海期連線", nCode);
            switch (nKind)
            {
                // 連線中斷
                case 3002:
                    _option.OsFutConnection = false;
                    break;
                // 網路斷線
                case 3021:
                    _option.OsFutConnection = false;
                    break;
                // 報價商品載入完成
                case 3003:
                case 3001:
                    _option.OsFutConnection = true;
                    break;
            }
            // 重置海期
            OSReset();
        }

        /// <summary>
        /// 海期報價商品清單資訊
        /// 交易所代碼,交易所名稱,商品報價代碼,商品名稱,最後交易日
        /// </summary>
        /// <param name="bstrValue"></param>
        private void m_SKOSQuoteLib_OnOverseaProducts(string bstrValue)
        {
            var stock = bstrValue.Split(",");
            if (DateTime.TryParseExact(stock[4], "yyyyMMdd", null, System.Globalization.DateTimeStyles.None, out DateTime lastTime))
            {

                _stockList.Add(new Data.Entities.Captial()
                {
                    Exchange = stock[0],
                    Code = stock[2],
                    Name = stock[3],
                    LastTradeDay = lastTime,
                    OrderID = stock[2],
                    MarketNo = 7
                });
            }

            //_logger.LogInformation(bstrValue);
        }

        /// <summary>
        /// 回傳技術分析資訊
        /// </summary>
        /// <param name="bstrStockNo">股票代碼</param>
        /// <param name="bstrData">資料 目前皆使用新版1分線</param>
        void m_SKOSQuoteLib_OnNotifyKLineDataOS(string bstrStockNo, string bstrData)
        {
            //_logger.LogInformation(bstrData);
            var temp = bstrData.Split(",");
            DateTime date;
            if (temp[0].Length == 10)
                DateTime.TryParseExact(temp[0], "yyyy/MM/dd", null, System.Globalization.DateTimeStyles.None, out date);
            else
                DateTime.TryParseExact(temp[0], "yyyy/MM/dd HH:mm", null, System.Globalization.DateTimeStyles.None, out date);

            _kLinesByExchange[_OSExchange].Add(new CaptialKLine
            {
                Exchange = _OSExchange,
                Code = bstrStockNo,
                Date = date,
                Open = Convert.ToSingle(temp[1]),
                High = Convert.ToSingle(temp[2]),
                Low = Convert.ToSingle(temp[3]),
                Close = Convert.ToSingle(temp[4]),
                Volume = Convert.ToInt32(temp[5])
            });
        }

        /// <summary>
        /// 歷史Tick 回傳
        /// </summary>
        /// <param name="nIndex">系統所編的索引代碼</param>
        /// <param name="nPtr">表示資料的位址(Key)</param>
        /// <param name="nDate">交易日期。(YYYYMMDD)</param>
        /// <param name="nTime">時間。(時：分：秒’毫秒"微秒)</param>
        /// <param name="nClose">成交價</param>
        /// <param name="nQty">成交量</param>
        void m_SKOSQuoteLib_OnNotifyHistoryTicksNineDigitLONG(int nIndex, int nPtr, int nDate, int nTime, long nClose, int nQty)
        {
            //_logger.LogInformation($"[海期][歷史Tick]{nIndex} {nPtr} {nDate} {nTime} {nClose} {nQty}");

            TickLine tick = new TickLine
            {
                SMarketNo = 0,
                NIndex = nIndex,
                NPtr = nPtr,
                NDate = nDate,
                NTimehms = nTime,
                NTimemillismicros = 0,
                NBid = 0,
                NAsk = 0,
                NClose = (float)nClose, // Initialize with raw nClose, then scale if needed
                NQty = nQty,
                NSimulate = 0
            };

            ChartKLine tempChart;
            if (_tickIndexOS != nIndex)
            {
                // 判斷tick所屬chart
                tempChart = _chartKLine.FirstOrDefault(a => a.SIndex == -1 && a.Exchange != "TAIFEX");
                if (tempChart == null)
                {
                    // _logger.LogWarning("[m_SKOSQuoteLib_OnNotifyHistoryTicksNineDigitLONG] No available chart found for new tick.");
                    return;
                }
                tempChart.SIndex = nIndex;
                _tickIndexOS = nIndex;
                // Apply scaling based on exchange
                if (tempChart.Exchange != "CBOT") // Assuming /100F is for non-CBOT international
                {
                    tick.NClose = nClose / 100F;
                }
                // If tempChart.Exchange == "CBOT", tick.NClose remains as (float)nClose, assuming nClose is already the correct price.
            }
            else
            {
                tempChart = _chartKLine.SingleOrDefault(a => a.SIndex == nIndex && a.Exchange != "TAIFEX");
                if (tempChart == null)
                {
                    // _logger.LogWarning("[m_SKOSQuoteLib_OnNotifyHistoryTicksNineDigitLONG] No matching chart found for index {nIndex}", nIndex);
                    return;
                }
                // Apply scaling based on exchange
                if (tempChart.Exchange != "CBOT") // Assuming /100F is for non-CBOT international
                {
                    tick.NClose = nClose / 100F;
                }
                // If tempChart.Exchange == "CBOT", tick.NClose remains as (float)nClose, assuming nClose is already the correct price.
            }
            if (nClose != 0)
            {
                for (sbyte cycle = 2; cycle <= 5; cycle++)
                {
                    tempChart.AddHistoryTickOS(tick, cycle);
                }
            }
        }


        /*/// <summary>
        /// 歷史Tick 回傳
        /// </summary>
        /// <param name="nIndex">系統所編的索引代碼</param>
        /// <param name="nPtr">表示資料的位址(Key)</param>
        /// <param name="nDate">交易日期。(YYYYMMDD)</param>
        /// <param name="nTime">時間。(時：分：秒’毫秒"微秒)</param>
        /// <param name="nClose">成交價</param>
        /// <param name="nQty">成交量</param>
        void m_SKOSQuoteLib_OnNotifyHistoryTicks(short nIndex, int nPtr, int nDate, int nTime, int nClose, int nQty)
        {
            _logger.LogInformation($"[海期][歷史Tick]{nIndex} {nPtr} {nDate} {nTime} {nClose} {nQty}");

            TickLine tick = new TickLine
            {
                SMarketNo = 0,
                NIndex = nIndex,
                NPtr = nPtr,
                NDate = nDate,
                NTimehms = nTime,
                NTimemillismicros = 0,
                NBid = 0,
                NAsk = 0,
                NClose = nClose / 100F,
                NQty = nQty,
                NSimulate = 0
            };

            if (_tickIndexOS != nIndex)
            {
                // 判斷tick所屬chart
                var tempChart = _chartKLine.First(a => a.SIndex == -1);
                tempChart.SIndex = nIndex;
                _tickIndexOS = nIndex;
                if (tempChart.Exchange == "CBOT")
                    tick.NClose = nClose;
                if (nClose != 0)
                {
                    tempChart.AddHistoryTickOS(tick);
                }
            }
            else
            {
                var tempChart = _chartKLine.Single(a => a.SIndex == nIndex);
                if (tempChart.Exchange == "CBOT")
                    tick.NClose = nClose;
                if (nClose != 0)
                {
                    tempChart.AddHistoryTickOS(tick);
                }
            }
        }*/

        /// <summary>
        /// 即時Tick 回傳
        /// </summary>
        /// <param name="nIndex">系統所編的索引代碼</param>
        /// <param name="nPtr">表示資料的位址(Key)</param>
        /// <param name="nDate">交易日期。(YYYYMMDD)</param>
        /// <param name="nTime">時間。(時：分：秒’毫秒"微秒)</param>
        /// <param name="nClose">成交價</param>
        /// <param name="nQty">成交量</param>
        private void m_SKOSQuoteLib_OnNotifyTicksNineDigitLONG(int nIndex, int nPtr, int nDate, int nTime, long nClose, int nQty)
        {
            //_logger.LogInformation($"[海期][即時Tick]{nIndex} {nPtr} {nDate} {nTime} {nClose} {nQty}");
            try
            {
                TickLine tick = new TickLine
                {
                    SMarketNo = 0,
                    NIndex = nIndex,
                    NPtr = nPtr,
                    NDate = nDate,
                    NTimehms = nTime,
                    NTimemillismicros = 0,
                    NBid = 0,
                    NAsk = 0,
                    NClose = (float)nClose, // Initialize with raw nClose, then scale if needed
                    NQty = nQty,
                    NSimulate = 0
                };

                var tempChart = _chartKLine.SingleOrDefault(a => a.SIndex == nIndex && a.Exchange != "TAIFEX");
                if (tempChart == null)
                    return;
                
                // Apply scaling based on exchange
                if (tempChart.Exchange != "CBOT") // Assuming /100F is for non-CBOT international
                {
                    tick.NClose = nClose / 100F;
                }
                // If tempChart.Exchange == "CBOT", tick.NClose remains as (float)nClose, assuming nClose is already the correct price.
                if (nClose != 0)
                {
                    for (sbyte cycle = 1; cycle <= 5; cycle++)
                    {
                        BaseKLine temp;
                        switch (cycle)
                        {
                            case 1: temp = tempChart.KLine1.Last(); break;
                            case 2: temp = tempChart.KLine5.Last(); break;
                            case 3: temp = tempChart.KLine15.Last(); break;
                            case 4: temp = tempChart.KLine30.Last(); break;
                            case 5: temp = tempChart.KLine60.Last(); break;
                            //case 6: temp = tempChart.KLineD.Last(); break;
                            case 9: temp = tempChart.KLine2H.Last(); break;
                            default: continue;
                        }
                        // 更新K線並判斷是否為新K
                        bool isNewBar = tempChart.AddNotifyTickOS(tick, cycle);

                        // 不論是否為新K棒，都進行策略判斷 (實現即時停損)
                        if (tempChart.Option != null)
                        {
                            if (isNewBar)
                            {
                                _logger.LogInformation("新增K線{Code} {Date} {Open} {Close}", tempChart.Code, temp.Date, temp.Open, temp.Close);
                                // 特定情況通知
                                if (cycle == 2 && tempChart.KLine5.SkipLast(1).Last().High >= tempChart.KLine5.SkipLast(1).Last().BBUB)
                                {
                                    SendLineMsg($"[{tempChart.Code}][5分][布林通道][上緣]觸價通知");
                                }
                                else if (cycle == 2 && tempChart.KLine5.SkipLast(1).Last().Low <= tempChart.KLine5.SkipLast(1).Last().BBLB)
                                {
                                    SendLineMsg($"[{tempChart.Code}][5分][布林通道][下緣]觸價通知");
                                }
                            }

                            // 判斷有相同週期策略
                            if (tempChart.Strategy != null && tempChart.Strategy.Any(a => a.Cycle == cycle))
                            {
                                var stratehys = tempChart.Strategy.Where(a => a.Cycle == cycle);
                                // 迴圈策略
                                foreach (var strategy in stratehys)
                                {
                                    // 取得最後一筆交易
                                    List<CaptialTradeHistory> historys;
                                    using (var scope = _serviceScopeFactory.CreateScope())
                                    {
                                        var db = scope.ServiceProvider.GetRequiredService<DBContext>();
                                        if (tempChart.Option.IsFake)
                                            historys = db.CaptialTradeHistory.Where(w => w.ChartId == tempChart.Id && w.IsFake && w.StrategyId == strategy.Id).ToList();
                                        else
                                            historys = db.CaptialTradeHistory.Where(w => w.ChartId == tempChart.Id && !w.IsFake && w.IsDeal && w.StrategyId == strategy.Id).ToList();
                                    }

                                    var groups = historys.GroupBy(g => g.TradeId).ToList();
                                    var history = groups.LastOrDefault(w => w.Count() == 1);
                                    if (history != null)
                                    {
                                        var tempHistory = history.First();
                                        var result = _futures.PublicStrategy(tempChart, tempHistory, tempHistory.TradeId, strategy.Cycle, strategy.Strategy, !isNewBar);
                                        if (result != SignalType.Non)
                                        {
                                            _logger.LogInformation("[{Code}]result {Result}", tempChart.Code, result);
                                            SeanOrder(result, tempChart, tempHistory, tempHistory.TradeId, strategy);
                                        }
                                    }
                                    else if (isNewBar) // 只在新K棒時判斷進場
                                    {
                                        uint maxId;
                                        using (var scope = _serviceScopeFactory.CreateScope())
                                        {
                                            var db = scope.ServiceProvider.GetRequiredService<DBContext>();
                                            maxId = db.CaptialTradeHistory.Any(w => w.ChartId == tempChart.Id) ? db.CaptialTradeHistory.Where(w => w.ChartId == tempChart.Id).Max(m => m.TradeId) : 0;
                                        }
                                        var result = _futures.PublicStrategy(tempChart, null, maxId, strategy.Cycle, strategy.Strategy, false);
                                        if (result != SignalType.Non)
                                        {
                                            _logger.LogInformation("[{Code}]result {Result}", tempChart.Code, result);
                                            SeanOrder(result, tempChart, null, maxId, strategy);
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "[OnNotifyTicks] Error for index {Index}", nIndex);
            }
        }

        /*/// <summary>
        /// 即時Tick 回傳
        /// </summary>
        /// <param name="nIndex">系統所編的索引代碼</param>
        /// <param name="nPtr">表示資料的位址(Key)</param>
        /// <param name="nDate">交易日期。(YYYYMMDD)</param>
        /// <param name="nTime">時間。(時：分：秒’毫秒"微秒)</param>
        /// <param name="nClose">成交價</param>
        /// <param name="nQty">成交量</param>
        private void m_SKOSQuoteLib_OnNotifyTicks(short nIndex, int nPtr, int nDate, int nTime, int nClose, int nQty)
        {
            Console.WriteLine($"[海期][即時Tick]{nIndex} {nPtr} {nDate} {nTime} {nClose} {nQty}");
            try
            {
                TickLine tick = new TickLine
                {
                    SMarketNo = 0,
                    NIndex = nIndex,
                    NPtr = nPtr,
                    NDate = nDate,
                    NTimehms = nTime,
                    NTimemillismicros = 0,
                    NBid = 0,
                    NAsk = 0,
                    NClose = nClose / 100F,
                    NQty = nQty,
                    NSimulate = 0
                };

                var tempChart = _chartKLine.Single(a => a.SIndex == nIndex);
                if (tempChart.Exchange == "CBOT")
                    tick.NClose = nClose;
                if (nClose != 0)
                {
                    var temp = tempChart.KLine.Last();
                    // 新增Tick 回傳為True時判斷交易
                    if (tempChart.Option != null && tempChart.AddNotifyTickOS(tick))
                    {
                        Console.WriteLine($"新增K線{tempChart.Code} {temp.Date} {temp.Open} {temp.Close}");
                        // 取得最後一筆交易
                                                List<CaptialTradeHistory> historys;
                                                if (tempChart.Option.IsFake)
                                                    historys = CaptialTradeHistory.Where(w => w.ChartId == tempChart.Id && w.IsFake).ToList();
                                                else
                                                    historys = CaptialTradeHistory.Where(w => w.ChartId == tempChart.Id && !w.IsFake && w.IsDeal).ToList();
                        
                                                var groups = historys.GroupBy(g => g.TradeId).ToList();
                                                var history = groups.LastOrDefault(w => w.Count() == 1);
                                                if (history != null)
                                                {
                                                    var tempHistory = history.First();
                                                    Console.WriteLine($"tempHistory {tempHistory.Target} {tempHistory.Date} {tempHistory.Price} {tempHistory.B_S}");
                                                    var result = _futures.PublicStrategy(tempChart, tempHistory, tempHistory.TradeId);
                                                    Console.WriteLine($"[{tempChart.Code}]result {result}");
                                                    SeanOrder(result, tempChart, tempHistory, tempHistory.TradeId);
                                                }
                                                else
                                                {
                                                    uint maxId = CaptialTradeHistory.Any(w => w.ChartId == tempChart.Id) ? CaptialTradeHistory.Where(w => w.ChartId == tempChart.Id).Max(m => m.TradeId) : 0;
                                                    var result = _futures.PublicStrategy(tempChart, null, maxId);
                                                    Console.WriteLine($"[{tempChart.Code}]result {result}");
                                                    SeanOrder(result, tempChart, null, maxId);
                                                }                    }
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[OnNotifyTicks]{ex.Message}");
            }
        }*/

        private void OSReset()
        {

        }
        #endregion

        private void AddTickToFKline(TickLine tick)
        {
            // 解析日期 時間
            int yyyy = tick.NDate / 10000;
            int MM = tick.NDate / 100 % 100;
            int dd = tick.NDate % 100;
            int HH = tick.NTimehms / 10000;
            int mm = tick.NTimehms / 100 % 100;
            int ss = tick.NTimehms % 100;
            DateTime ticktime = new DateTime(yyyy, MM, dd, HH, mm, ss);

            int newMM;
            if (HH >= 8 && HH <= 14)
                newMM = 45;
            else
                newMM = 0;

            if (ticktime.Hour == 14)
                return;

            if (_fKLine.Any(a => a.Date >= ticktime && a.Date < ticktime.AddMonths(1)))
            {
                var kline = _fKLine.Single(s => s.Date >= ticktime && s.Date < ticktime.AddMonths(60));
                if (kline.High < tick.NClose)
                    kline.High = tick.NClose;
                if (kline.Low > tick.NClose)
                    kline.Low = tick.NClose;
                kline.Close = tick.NClose;
                kline.Volume += tick.NQty;
            }
            else
            {
                CaptialKLine tempKline = new CaptialKLine
                {
                    Date = new DateTime(yyyy, MM, dd, HH, mm, 00).AddMinutes(1),
                    Open = tick.NClose,
                    High = tick.NClose,
                    Low = tick.NClose,
                    Close = tick.NClose,
                    Volume = tick.NQty,
                };

                _fKLine.Add(tempKline);
                _logger.LogDebug("New KLine added: {KLineJson}", JsonConvert.SerializeObject(tempKline));

                // 下單判斷
            }
        }

        /// <summary>
        /// 設定多時K線
        /// </summary>
        private void SetTAKline(bool isHistory = true)
        {
            if (isHistory)
            {

                foreach (var kline in _fKLine)
                {
                    #region 設定月線
                    if (_taKline.M.Any(a => a.Date.Year == kline.Date.Year && a.Date.Month == kline.Date.Month))
                    {
                        BaseKLine temp = _taKline.M.Single(a => a.Date.Year == kline.Date.Year && a.Date.Month == kline.Date.Month);
                        MixKLine(ref temp, kline);
                    }
                    else
                    {
                        _taKline.M.Add(kline.ToBaseKline());
                    }
                    #endregion
                    #region 設定周線
                    if (_taKline.W.Any(a => a.Date.IsInSameWeek(kline.Date)))
                    {
                        BaseKLine temp = _taKline.W.Single(a => a.Date.Year == kline.Date.Year && a.Date.Month == kline.Date.Month);
                        MixKLine(ref temp, kline);
                    }
                    else
                    {
                        _taKline.W.Add(kline.ToBaseKline());
                    }
                    #endregion
                    #region 設定日線
                    if (_taKline.D.Any(a => a.Date > kline.Date.AddDays(-1)))
                    {
                        BaseKLine temp = _taKline.D.Single(a => a.Date.Year == kline.Date.Year && a.Date.Month == kline.Date.Month);
                        MixKLine(ref temp, kline);
                    }
                    else
                    {
                        _taKline.D.Add(kline.ToBaseKline());
                    }
                    #endregion
                    #region 設定60分線
                    if (_taKline.D.Any(a => a.Date > kline.Date.AddMinutes(-60)))
                    {
                        BaseKLine temp = _taKline.M60.Single(a => a.Date.Year == kline.Date.Year && a.Date.Month == kline.Date.Month);
                        MixKLine(ref temp, kline);
                    }
                    else
                    {
                        _taKline.M60.Add(kline.ToBaseKline());
                    }
                    #endregion
                    #region 設定30分線
                    if (_taKline.D.Any(a => a.Date > kline.Date.AddMinutes(-30)))
                    {
                        BaseKLine temp = _taKline.M30.Single(a => a.Date.Year == kline.Date.Year && a.Date.Month == kline.Date.Month);
                        MixKLine(ref temp, kline);
                    }
                    else
                    {
                        _taKline.M30.Add(kline.ToBaseKline());
                    }
                    #endregion
                    #region 設定15分線
                    if (_taKline.D.Any(a => a.Date > kline.Date.AddMinutes(-15)))
                    {
                        BaseKLine temp = _taKline.M15.Single(a => a.Date.Year == kline.Date.Year && a.Date.Month == kline.Date.Month);
                        MixKLine(ref temp, kline);
                    }
                    else
                    {
                        _taKline.M15.Add(kline.ToBaseKline());
                    }
                    #endregion
                    #region 設定5分線
                    if (_taKline.D.Any(a => a.Date > kline.Date.AddMinutes(-5)))
                    {
                        BaseKLine temp = _taKline.M5.Single(a => a.Date.Year == kline.Date.Year && a.Date.Month == kline.Date.Month);
                        MixKLine(ref temp, kline);
                    }
                    else
                    {
                        _taKline.M5.Add(kline.ToBaseKline());
                    }
                    #endregion
                    #region 設定1分線
                    _taKline.M1.Add(kline.ToBaseKline());
                    #endregion
                }
            }
            else
            {

            }
        }

        private void MixKLine(ref BaseKLine @base, CaptialKLine mix)
        {
            if (@base.High < mix.High)
                @base.High = mix.High;
            if (@base.Low > mix.Low)
                @base.Low = mix.Low;
            @base.Close = mix.Close;
            @base.Volume += mix.Volume;
        }

        private DateTime PreviousWorkingDay(DateTime date)
        {
            using (var scope = _serviceScopeFactory.CreateScope())
            {
                var db = scope.ServiceProvider.GetRequiredService<DBContext>();
                var list = db.Holiday.Where(w => w.Date > DateTime.Now.AddMonths(-1) && w.Date < DateTime.Now).ToList();

                int offset = 0;
                while (offset <= 0 && offset > -100)
                {
                    date.AddDays(offset);
                    if (date.DayOfWeek == DayOfWeek.Sunday || date.DayOfWeek == DayOfWeek.Saturday)
                    {
                        if (list.Any(a => a.Date == date && a.Float == "P"))
                            return date;
                        else
                            offset--;
                    }
                    else
                    {
                        if (list.Any(a => a.Date == date && a.Float == "M"))
                            offset--;
                        else
                            return date;
                    }
                }
                return date;
            }
        }

        private List<CaptialKLineCycle> SetCycleKLine(sbyte cycle, List<CaptialKLine> kLines)
        {
            DateTime minDate, maxDate, tempDate;
            List<CaptialKLineCycle> result = new List<CaptialKLineCycle>();
            List<CaptialKLineCycle> add = new List<CaptialKLineCycle>();
            List<CaptialKLineCycle> update = new List<CaptialKLineCycle>();
            
            switch (cycle)
            {
                case 1:
                    result = kLines.Select(s => new CaptialKLineCycle
                    {
                        Date = s.Date,
                        Code = s.Code,
                        Exchange = s.Exchange,
                        Cycle = cycle,
                        Open = s.Open,
                        High = s.High,
                        Low = s.Low,
                        Close = s.Close,
                        Volume = s.Volume
                    }).ToList();
                    Upsert(result);
                    break;
                case 2:
                    minDate = kLines.Min(s => s.Date);
                    maxDate = kLines.Max(s => s.Date);
                    tempDate = new DateTime(minDate.Ticks).Date;
                    while (tempDate <= maxDate)
                    {
                        if (kLines.First().Exchange == "TAIFEX")
                        {
                            if (tempDate.Hour == 8 && tempDate.Minute <= 50)
                                tempDate = tempDate.Date + new TimeSpan(8, 50, 0);
                            else if (tempDate.Hour == 15 && tempDate.Minute <= 5)
                                tempDate = tempDate.Date + new TimeSpan(15, 5, 0);
                        }

                        List<CaptialKLine> temp = kLines.Where(s => tempDate.AddMinutes(-5) < s.Date && s.Date <= tempDate).OrderBy(o => o.Date).ToList();
                        if (temp.Count == 0)
                        {
                            tempDate = tempDate.AddMinutes(5);
                            continue;
                        }

                        CaptialKLineCycle newKLine = new CaptialKLineCycle
                        {
                            Date = tempDate,
                            Exchange = temp.First().Exchange,
                            Code = temp.First().Code,
                            Cycle = cycle,
                            Open = temp.First().Open,
                            High = temp.Max(m => m.High),
                            Low = temp.Min(m => m.Low),
                            Close = temp.Last().Close,
                            Volume = temp.Sum(m => m.Volume)
                        };
                        result.Add(newKLine);
                        tempDate = tempDate.AddMinutes(5);
                    }
                    Upsert(result);
                    break;
                case 3:
                    minDate = kLines.Min(s => s.Date);
                    maxDate = kLines.Max(s => s.Date);
                    tempDate = new DateTime(minDate.Ticks).Date;
                    while (tempDate <= maxDate)
                    {
                        if (kLines.First().Exchange == "TAIFEX")
                        {
                            if (tempDate.Hour == 8)
                                tempDate = tempDate.Date + new TimeSpan(9, 0, 0);
                            else if (tempDate.Hour == 15 && tempDate.Minute <= 15)
                                tempDate = tempDate.Date + new TimeSpan(15, 15, 0);
                        }
                        
                        List<CaptialKLine> temp = kLines.Where(s => tempDate.AddMinutes(-15) < s.Date && s.Date <= tempDate).OrderBy(o => o.Date).ToList();
                        if (temp.Count == 0)
                        {
                            tempDate = tempDate.AddMinutes(15);
                            continue;
                        }

                        CaptialKLineCycle newKLine = new CaptialKLineCycle
                        {
                            Date = tempDate,
                            Exchange = temp.First().Exchange,
                            Code = temp.First().Code,
                            Cycle = cycle,
                            Open = temp.First().Open,
                            High = temp.Max(m => m.High),
                            Low = temp.Min(m => m.Low),
                            Close = temp.Last().Close,
                            Volume = temp.Sum(m => m.Volume)
                        };
                        result.Add(newKLine);
                        tempDate = tempDate.AddMinutes(15);
                    }
                    Upsert(result);
                    break;
                case 4:
                    minDate = kLines.Min(s => s.Date);
                    maxDate = kLines.Max(s => s.Date);
                    tempDate = new DateTime(minDate.Ticks).Date;
                    while (tempDate <= maxDate)
                    {
                        if (kLines.First().Exchange == "TAIFEX")
                        {
                            if (tempDate.Hour == 8)
                                tempDate = tempDate.Date + new TimeSpan(9, 15, 0);
                            else if (tempDate.Hour == 15 && tempDate.Minute <= 30)
                                tempDate = tempDate.Date + new TimeSpan(15, 30, 0);
                        }

                        List<CaptialKLine> temp = kLines.Where(s => tempDate.AddMinutes(-30) < s.Date && s.Date <= tempDate).OrderBy(o => o.Date).ToList();
                        if (temp.Count == 0)
                        {
                            tempDate = tempDate.AddMinutes(30);
                            continue;
                        }

                        CaptialKLineCycle newKLine = new CaptialKLineCycle
                        {
                            Date = tempDate,
                            Exchange = temp.First().Exchange,
                            Code = temp.First().Code,
                            Cycle = cycle,
                            Open = temp.First().Open,
                            High = temp.Max(m => m.High),
                            Low = temp.Min(m => m.Low),
                            Close = temp.Last().Close,
                            Volume = temp.Sum(m => m.Volume)
                        };
                        result.Add(newKLine);
                        tempDate = tempDate.AddMinutes(30);
                    }
                    Upsert(result);
                    break;
                case 5:
                    minDate = kLines.Min(s => s.Date);
                    maxDate = kLines.Max(s => s.Date);
                    tempDate = new DateTime(minDate.Ticks).Date;
                    while (tempDate <= maxDate)
                    {
                        if (kLines.First().Exchange == "TAIFEX")
                        {
                            if (tempDate.Hour == 8)
                                tempDate = tempDate.Date + new TimeSpan(9, 45, 0);
                            else if (tempDate.Hour == 15)
                                tempDate = tempDate.Date + new TimeSpan(16, 0, 0);
                        }

                        List<CaptialKLine> temp = kLines.Where(s => tempDate.AddHours(-1) < s.Date  && s.Date <= tempDate).OrderBy(o => o.Date).ToList();
                        if (temp.Count == 0)
                        {
                            tempDate = tempDate.AddHours(1);
                            continue;
                        }

                        CaptialKLineCycle newKLine = new CaptialKLineCycle
                        {
                            Date = tempDate,
                            Exchange = temp.First().Exchange,
                            Code = temp.First().Code,
                            Cycle = cycle,
                            Open = temp.First().Open,
                            High = temp.Max(m => m.High),
                            Low = temp.Min(m => m.Low),
                            Close = temp.Last().Close,
                            Volume = temp.Sum(m => m.Volume)
                        };
                        result.Add(newKLine);
                        tempDate = tempDate.AddHours(1);
                    }
                    Upsert(result);
                    break;
                case 6: // 日K線
                    result = GenerateDailyKLines(kLines, cycle);
                    Upsert(result);
                    break;
                case 7: // 週K線
                    {
                        // 先生成日K線
                        var dailyKLines = GenerateDailyKLines(kLines, 6);

                        // 按交易所分組
                        var groupedByExchange = dailyKLines.GroupBy(k => k.Exchange).ToList();

                        foreach (var exchangeGroup in groupedByExchange)
                        {
                            string exchange = exchangeGroup.Key;
                            var exchangeKLines = exchangeGroup.OrderBy(k => k.Date).ToList();
                            if (!exchangeKLines.Any()) continue;

                            minDate = exchangeKLines.Min(k => k.Date);
                            maxDate = exchangeKLines.Max(k => k.Date);

                            // 從第一個週一開始
                            tempDate = minDate.Date.AddDays(-(int)minDate.DayOfWeek + (int)DayOfWeek.Monday);
                            bool isDST = TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time").IsDaylightSavingTime(tempDate);
                            int offset = isDST ? 1 : 0; // 夏令時間提早 1 小時
                            switch (exchange)
                            {
                                case "TAIFEX":
                                    tempDate = tempDate.AddHours(8).AddMinutes(45);
                                    break;
                                case "NYM":
                                case "CME":
                                    tempDate = tempDate.AddHours(7 - offset);
                                    break;
                                case "CBOT":
                                    tempDate = tempDate.AddHours(9 - offset);
                                    break;
                                default:
                                    tempDate = tempDate.AddHours(8).AddMinutes(45);
                                    break;
                            }

                            while (tempDate <= maxDate)
                            {
                                // 定義一週的範圍：週一開始到週日結束
                                DateTime startOfWeek = tempDate;
                                DateTime endOfWeek = startOfWeek.AddDays(7);

                                var temp = exchangeKLines
                                    .Where(k => k.Date >= startOfWeek && k.Date < endOfWeek)
                                    .OrderBy(k => k.Date)
                                    .ToList();

                                if (temp.Count == 0)
                                {
                                    tempDate = tempDate.AddDays(7);
                                    continue;
                                }

                                var newKLine = new CaptialKLineCycle
                                {
                                    Date = startOfWeek,
                                    Exchange = exchange,
                                    Code = temp.First().Code,
                                    Cycle = cycle,
                                    Open = temp.First().Open,
                                    High = temp.Max(k => k.High),
                                    Low = temp.Min(k => k.Low),
                                    Close = temp.Last().Close,
                                    Volume = temp.Sum(k => k.Volume)
                                };
                                result.Add(newKLine);
                                tempDate = tempDate.AddDays(7); // 移到下一週
                            }
                        }
                    }
                    Upsert(result);
                    break;
                case 8:
                    minDate = kLines.Min(s => s.Date);
                    maxDate = kLines.Max(s => s.Date);
                    for (int year = minDate.Year; year <= maxDate.Year; year++)
                    {
                        for (int month = 1; month <= 12; month++)
                        {
                            tempDate = new DateTime(year, month, 1);
                            List<CaptialKLine> temp = kLines.Where(s => s.Date >= tempDate && s.Date < tempDate.AddMonths(1)).OrderBy(o => o.Date).ToList();
                            if (temp.Count == 0)
                                continue;
                            CaptialKLineCycle newKLine = new CaptialKLineCycle
                            {
                                Date = tempDate,
                                Exchange = temp.First().Exchange,
                                Code = temp.First().Code,
                                Cycle = 8,
                                Open = temp.First().Open,
                                High = temp.Max(m => m.High),
                                Low = temp.Min(m => m.Low),
                                Close = temp.Last().Close,
                                Volume = temp.Sum(m => m.Volume)
                            };
                            result.Add(newKLine);
                        }
                    }
                    Upsert(result);
                    break;
                case 9:
                    minDate = kLines.Min(s => s.Date);
                    maxDate = kLines.Max(s => s.Date);
                    tempDate = new DateTime(minDate.Ticks).Date;
                    while (tempDate <= maxDate)
                    {
                        if (kLines.First().Exchange == "TAIFEX")
                        {
                            if (tempDate.Hour == 8)
                                tempDate = tempDate.Date + new TimeSpan(9, 45, 0);
                            else if (tempDate.Hour == 15)
                                tempDate = tempDate.Date + new TimeSpan(16, 0, 0);
                        }

                        List<CaptialKLine> temp = kLines.Where(s => tempDate.AddHours(-2) < s.Date && s.Date <= tempDate).OrderBy(o => o.Date).ToList();
                        if (temp.Count == 0)
                        {
                            tempDate = tempDate.AddHours(2);
                            continue;
                        }

                        CaptialKLineCycle newKLine = new CaptialKLineCycle
                        {
                            Date = tempDate,
                            Exchange = temp.First().Exchange,
                            Code = temp.First().Code,
                            Cycle = cycle,
                            Open = temp.First().Open,
                            High = temp.Max(m => m.High),
                            Low = temp.Min(m => m.Low),
                            Close = temp.Last().Close,
                            Volume = temp.Sum(m => m.Volume)
                        };
                        result.Add(newKLine);
                        tempDate = tempDate.AddHours(2);
                    }
                    Upsert(result);
                    break;
                default:
                    throw new Exception("週期異常");
            }

            return new List<CaptialKLineCycle>();
        }


        private void Upsert(List<CaptialKLineCycle> cycles)
        {
            using (var scope = _serviceScopeFactory.CreateScope())
            {
                var db = scope.ServiceProvider.GetRequiredService<DBContext>();
                foreach (CaptialKLineCycle cycle in cycles)
                {
                    var exist = db!.CaptialKLineCycle.FirstOrDefault(o => o.Date == cycle.Date && o.Cycle == cycle.Cycle && o.Code == cycle.Code);
                    if (exist == null)
                    {
                        db.CaptialKLineCycle.Add(cycle);
                    }
                    else
                    {
                        db.Entry(exist).CurrentValues.SetValues(cycle);
                    }
                }

                db.SaveChanges();
            }
        }

        /// <summary>
        /// 載入週期K線
        /// </summary>
        private void LoadingChartKLine(CaptialChart chart)
        {
            using (var scope = _serviceScopeFactory.CreateScope())
            {
                var db = scope.ServiceProvider.GetRequiredService<DBContext>();
                for(sbyte cycle = 1;cycle <= 9; cycle++)
                {
                    if (cycle > 6 && cycle < 9) continue; // Skip 7 and 8 if they are not used

                    List<BaseKLine> kLines = db.CaptialKLineCycle
                    .Where(w => w.Code == chart.CaptialCode && w.Cycle == cycle && w.Exchange == chart.CaptialExchange)
                    .OrderByDescending(o => o.Date)
                    .Take(1000)
                    .OrderBy(o => o.Date)
                    .Select(s => new BaseKLine
                    {
                        Date = s.Date,
                        Open = s.Open,
                        High = s.High,
                        Low = s.Low,
                        Close = s.Close,
                        Volume = s.Volume
                    }).ToList();

                    if (!kLines.Any()) continue;

                    // 技術分析
                    // Find the strategy for the current cycle to get TA parameters.
                    var relevantStrategy = chart.ChartStrategies?.FirstOrDefault(s => s.Cycle == cycle);
                    if (relevantStrategy == null)
                    {
                        // If no specific strategy is found for this cycle, create a default one for TA calculation.
                        relevantStrategy = new CaptialChartStrategy
                        {
                            BbPeriod = 20, BbMultiplier = 2.0f,
                            KcPeriod = 20, KcMultiplier = 2.0f,
                            TrendPeriod = 200,
                            MacdFastPeriod = 12, MacdSlowPeriod = 26, MacdSignalPeriod = 9,
                            StochKPeriod = 14, StochDPeriod = 3, StochSmoothingPeriod = 3
                        };
                    }

                    // Calculate TA for the entire list at once.
                    List<BaseKLine> resultKLine = _futures.TA(kLines, relevantStrategy);

                    var tempChart = _chartKLine.SingleOrDefault(s => s.Id == chart.Id);
                    if (tempChart == null)
                    {
                        _logger.LogError("週期K異常 {ChartId}", chart.Id);
                        continue;
                    }
                        
                    switch (cycle)
                    {
                        case 1:
                            tempChart.KLine1 = resultKLine;
                            break;
                        case 2: 
                            tempChart.KLine5 = resultKLine;
                            break;
                        case 3:
                            tempChart.KLine15 = resultKLine;
                            break;
                        case 4:
                            tempChart.KLine30 = resultKLine;
                            break;
                        case 5:
                            tempChart.KLine60 = resultKLine;
                            break;
                        case 6:
                            tempChart.KLineD = resultKLine;
                            break;
                        case 9:
                            tempChart.KLine2H = resultKLine;
                            break;
                    }
                }
            }
        }

        /// <summary>
        /// 根據交易信號發送訂單
        /// </summary>
        /// <param name="signal">交易信號類型</param>
        /// <param name="chart">圖表K線數據</param>
        /// <param name="history">歷史交易記錄 (如果有的話)</param>
        /// <param name="operateId">操作ID</param>
        /// <param name="strategy">圖表策略</param>
        private void SeanOrder(SignalType signal, ChartKLine chart, CaptialTradeHistory? history, uint operateId, CaptialChartStrategy strategy)
        {
            // 根據策略週期選擇K線數據
            List<BaseKLine> model = strategy.Cycle switch
            {
                1 => model = chart.KLine1.Take(chart.KLine1.Count() - 1).ToList(),
                2 => model = chart.KLine5.Take(chart.KLine5.Count() - 1).ToList(),
                3 => model = chart.KLine15.Take(chart.KLine15.Count() - 1).ToList(),
                4 => model = chart.KLine30.Take(chart.KLine30.Count() - 1).ToList(),
                5 => model = chart.KLine60.Take(chart.KLine60.Count() - 1).ToList(),
                6 => model = chart.KLineD.Take(chart.KLineD.Count() - 1).ToList(),
                9 => model = chart.KLine2H.Take(chart.KLine2H.Count() - 1).ToList(),
                _ => throw new NotImplementedException()
            };

            var now = model.Last();
            var option = chart.Option;
            bool isFake = option.IsFake;
            string target = GetTradingTarget(option);

            if (signal == SignalType.Non) return;

            var trades = ProcessSignal(signal, chart, now, history, operateId, strategy, target, isFake);
            SaveAndLogTrades(trades);
        }

        // 取得交易標的
        private string GetTradingTarget(CaptialTradeOption option)
        {
            using (var scope = _serviceScopeFactory.CreateScope())
            {
                var db = scope.ServiceProvider.GetRequiredService<DBContext>();
                var query = db.Captial
                    .Where(w => w.Code.Contains(option.Target) && w.LastTradeDay > DateTime.Now.AddDays(option.TransferOrderOffsetDays))
                    .OrderBy(o => o.LastTradeDay);

                return option.Target switch
                {
                    "MTX" or "TX" => query.First(w => w.Code.Length == option.Target.Length + 2 && w.Code != option.Target + "00").Code,
                    _ => query.First(w => w.Code.Length == option.Target.Length + 4 && w.Code != option.Target + "0000").Code
                };
            }
        }

        // 處理不同信號類型
        private List<CaptialTradeHistory> ProcessSignal(SignalType signal, ChartKLine chart, BaseKLine now, CaptialTradeHistory? history, uint operateId, CaptialChartStrategy strategy, string target, bool isFake)
        {
            var trades = new List<CaptialTradeHistory>();
            var option = chart.Option;

            // 創建交易記錄的輔助方法
            CaptialTradeHistory CreateTrade(bool isBuy, uint tradeId, string tradeTarget, uint volume, string orderNo = "") => new()
            {
                ChartId = chart.Id,
                Date = now.Date,
                B_S = isBuy,
                Price = now.Close,
                TradeId = tradeId,
                IsFake = isFake,
                Target = tradeTarget,
                Signal = (sbyte)signal,
                OrderNo = orderNo,
                Volume = volume,
                StrategyId = strategy.Id,
                High = now.High,
                Low = now.Low
            };

            // 下單的輔助方法
            string PlaceOrder(bool isBuy, string tradeTarget, int qty)
            {
                string resMsg = "";
                if (isFake) return resMsg;

                if (chart.Exchange == "TAIFEX")
                {
                    var futureOrder = new FUTUREORDER
                    {
                        bstrFullAccount = _option.FutAcct,
                        bstrStockNo = tradeTarget,
                        sTradeType = option.DomesticTradeType, // 使用配置的國內期貨交易類型
                        sBuySell = (short)(isBuy ? 0 : 1), // 0:買進, 1:賣出
                        sDayTrade = 0, // 非當沖
                        sNewClose = 2, // 自動
                        bstrPrice = "P", // 範圍市價
                        nQty = qty,
                        sReserved = 0 // 盤中
                    };
                    m_pSKOrder.SendFutureOrderCLR(_option.LoginID, false, ref futureOrder, out resMsg);
                    _logger.LogInformation("國內期貨下單結果: {ResultMessage}", resMsg);
                }
                else
                {
                    var overseaFutureOrder = new OVERSEAFUTUREORDER
                    {
                        bstrFullAccount = _option.OsFutAcct,
                        bstrExchangeNo = chart.Exchange,
                        bstrStockNo = tradeTarget.Substring(0, tradeTarget.Length - 4),
                        bstrYearMonth = "20" + tradeTarget.Substring(tradeTarget.Length - 4),
                        sBuySell = (short)(isBuy ? 0 : 1),
                        sNewClose = 0, // 新倉
                        sDayTrade = 0,
                        sTradeType = option.OverseaTradeType, // 使用配置的海外期貨交易類型
                        sSpecialTradeType = option.OverseaSpecialTradeType, // 使用配置的海外期貨特殊交易類型
                        nQty = qty
                    };
                    m_pSKOrder.SendOverseaFutureOrder(_option.LoginID, false, ref overseaFutureOrder, out resMsg);
                    _logger.LogInformation("海外期貨下單結果: {ResultMessage}", resMsg);
                }
                return resMsg;
            }

            switch (signal)
            {
                case SignalType.Buy:
                case SignalType.Sell:
                    var isBuy = signal == SignalType.Buy;
                    var orderNo = isFake ? $"FAKE-{DateTime.UtcNow:yyMMddHHmmssfff}" : PlaceOrder(isBuy, target, option.TradeQty);
                    trades.Add(CreateTrade(isBuy, operateId + 1, target, (uint)option.TradeQty, orderNo));
                    break;

                case SignalType.BuyStop:
                case SignalType.SellStop:
                case SignalType.TakeProfitSell:
                case SignalType.TakeProfitBuy:
                    isBuy = signal == SignalType.SellStop || signal == SignalType.TakeProfitBuy;
                    orderNo = isFake ? $"FAKE-{DateTime.UtcNow:yyMMddHHmmssfff}" : PlaceOrder(isBuy, history.Target, (int)history.Volume);
                    trades.Add(CreateTrade(isBuy, operateId, history.Target, history.Volume, orderNo));
                    break;

                case SignalType.BuyToSell:
                case SignalType.SellToBuy:
                case SignalType.BuyTransferOrder:
                case SignalType.SellTransferOrder:
                    isBuy = signal is SignalType.SellToBuy or SignalType.BuyTransferOrder;
                    var firstIsBuy = signal is SignalType.BuyToSell or SignalType.BuyTransferOrder ? false : true;
                    var timestamp = DateTime.UtcNow;
                    var orderNo1 = isFake ? $"FAKE-{timestamp:yyMMddHHmmssff}1" : PlaceOrder(firstIsBuy, history.Target, (int)history.Volume);
                    trades.Add(CreateTrade(firstIsBuy, operateId, history.Target, history.Volume, orderNo1));
                    var orderNo2 = isFake ? $"FAKE-{timestamp:yyMMddHHmmssff}2" : PlaceOrder(isBuy, target, option.TradeQty);
                    trades.Add(CreateTrade(isBuy, operateId + 1, target, (uint)option.TradeQty, orderNo2));
                    break;
            }

            return trades;
        }

        // 保存並記錄交易
        private void SaveAndLogTrades(List<CaptialTradeHistory> trades)
        {
            if (trades.Count == 0) return;

            using (var scope = _serviceScopeFactory.CreateScope())
            {
                var db = scope.ServiceProvider.GetRequiredService<DBContext>();
                foreach (var item in trades)
                {
                    _logger.LogInformation("下單 {Target} {Date} {BS} {Price}", item.Target, item.Date, (item.B_S ? "買" : "賣"), item.Price);
                    SendLineMsg($"下單[{item.Target}][{item.Date:yyyy-MM-dd HH:mm:ss}]" +
                                (item.IsFake ? "[測試單]" : "[正式單]") +
                                (item.B_S ? "買進" : "賣出") +
                                $"[{item.Volume}口][{item.Price}][{item.OrderNo}]");
                }

                db.CaptialTradeHistory.AddRange(trades);
                db.SaveChanges();
            }
        }

        private void SendLineMsg(string msg)
        {
            BackgroundJob.Enqueue<OneTimerJob>(e => e.LineNotify(msg));
        }

        private static List<CaptialKLineCycle> GenerateDailyKLines(List<CaptialKLine> kLines, sbyte cycle)
        {
            var result = new List<CaptialKLineCycle>();
            var minDate = kLines.Min(s => s.Date);
            var maxDate = kLines.Max(s => s.Date);
            var tempDate = new DateTime(minDate.Ticks).Date.AddHours(8).AddMinutes(45); // 初始從 08:45 開始

            while (tempDate <= maxDate)
            {
                DateTime startOfDay = tempDate;
                DateTime endOfDay;
                string exchange = kLines.FirstOrDefault(s => s.Date >= tempDate)?.Exchange ?? "TAIFEX";

                bool isDST = TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time").IsDaylightSavingTime(tempDate);
                int offset = isDST ? 1 : 0; // 夏令時間提早 1 小時

                switch (exchange)
                {
                    case "TAIFEX":
                        startOfDay = tempDate.Date.AddHours(8).AddMinutes(45); // 當天 08:45
                        endOfDay = tempDate.Date.AddDays(1).AddHours(5); // 次日 05:00
                        break;
                    case "NYM":
                    case "CME":
                        // 假設使用台灣時間（UTC+8），NYM/CME 交易日從 07:00（ET 18:00 前一天）到次日 06:00（ET 17:00）

                        startOfDay = tempDate.Date.AddHours(7 - offset); // NYM/CME
                        endOfDay = tempDate.Date.AddDays(1).AddHours(6); // 次日 06:00
                        break;
                    case "CBOT":
                        // CBOT 交易日從 09:00（ET 20:00 前一天）到次日 03:45（ET 14:45）
                        startOfDay = tempDate.Date.AddHours(9 - offset); // NYM/CME
                        endOfDay = tempDate.Date.AddDays(1).AddHours(3).AddMinutes(45); // 次日 03:45
                        break;
                    default:
                        // 預設使用 TAIFEX 時間
                        startOfDay = tempDate.Date.AddHours(8).AddMinutes(45);
                        endOfDay = tempDate.Date.AddDays(1).AddHours(5);
                        break;
                }

                var temp = kLines
                    .Where(s => s.Exchange == exchange && s.Date >= startOfDay && s.Date < endOfDay)
                    .OrderBy(o => o.Date)
                    .ToList();

                if (temp.Count > 0)
                {
                    var newKLine = new CaptialKLineCycle
                    {
                        Date = startOfDay,
                        Exchange = exchange,
                        Code = temp.First().Code,
                        Cycle = cycle,
                        Open = temp.First().Open,
                        High = temp.Max(m => m.High),
                        Low = temp.Min(m => m.Low),
                        Close = temp.Last().Close,
                        Volume = temp.Sum(m => m.Volume)
                    };
                    result.Add(newKLine);
                }
                tempDate = tempDate.AddDays(1);
            }
            return result;
        }
    }
}
