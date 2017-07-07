# encoding: UTF-8

"""
DualThrust交易策略
"""

from datetime import time

from vnpy.trader.vtObject import VtBarData
from vnpy.trader.vtConstant import EMPTY_STRING
from vnpy.trader.app.ctaStrategy.ctaTemplate import CtaTemplate


########################################################################
class DualThrustStrategy(CtaTemplate):
    """DualThrust交易策略"""
    className = 'DualThrustStrategy'
    author = u'用Python的交易员'

    # 策略参数
    fixedSize = 100
    k1 = 0.4
    k2 = 0.6

    initDays = 10

    # 策略变量
    bar = None                  # K线对象
    barMinute = EMPTY_STRING    # K线当前的分钟
    barList = []                # K线对象的列表

    dayOpen = 0
    dayHigh = 0
    dayLow = 0
    
    range = 0
    longEntry = 0
    shortEntry = 0
    exitTime = time(hour=14, minute=55)

    longEntered = False
    shortEntered = False

    orderList = []                      # 保存委托代码的列表

    # 参数列表，保存了参数的名称
    paramList = ['name',
                 'className',
                 'author',
                 'vtSymbol',
                 'k1',
                 'k2']    

    # 变量列表，保存了变量的名称
    varList = ['inited',
               'trading',
               'pos',
               'range',
               'longEntry',
               'shortEntry',
               'exitTime']  

    #----------------------------------------------------------------------
    def __init__(self, ctaEngine, setting):
        """Constructor"""
        super(DualThrustStrategy, self).__init__(ctaEngine, setting) 
        
        self.barList = []

    #----------------------------------------------------------------------
    def onInit(self):
        """初始化策略（必须由用户继承实现）"""
        self.writeCtaLog(u'%s策略初始化' %self.name)
    
        # 载入历史数据，并采用回放计算的方式初始化策略数值
        initData = self.loadBar(self.initDays)
        for bar in initData:
            self.onBar(bar)

        self.putEvent()

    #----------------------------------------------------------------------
    def onStart(self):
        """启动策略（必须由用户继承实现）"""
        self.writeCtaLog(u'%s策略启动' %self.name)
        self.putEvent()

    #----------------------------------------------------------------------
    def onStop(self):
        """停止策略（必须由用户继承实现）"""
        self.writeCtaLog(u'%s策略停止' %self.name)
        self.putEvent()

    #----------------------------------------------------------------------
    def onTick(self, tick):
        """收到行情TICK推送（必须由用户继承实现）"""
        # 计算K线
        tickMinute = tick.datetime.minute

        if tickMinute != self.barMinute:    
            if self.bar:
                self.onBar(self.bar)

            bar = VtBarData()              
            bar.vtSymbol = tick.vtSymbol
            bar.symbol = tick.symbol
            bar.exchange = tick.exchange

            bar.open = tick.lastPrice
            bar.high = tick.lastPrice
            bar.low = tick.lastPrice
            bar.close = tick.lastPrice

            bar.date = tick.date
            bar.time = tick.time
            bar.datetime = tick.datetime    # K线的时间设为第一个Tick的时间

            self.bar = bar                  # 这种写法为了减少一层访问，加快速度
            self.barMinute = tickMinute     # 更新当前的分钟
        else:                               # 否则继续累加新的K线
            bar = self.bar                  # 写法同样为了加快速度

            bar.high = max(bar.high, tick.lastPrice)
            bar.low = min(bar.low, tick.lastPrice)
            bar.close = tick.lastPrice

    #----------------------------------------------------------------------
    def onBar(self, bar):
        """收到Bar推送（必须由用户继承实现）"""
        # 撤销之前发出的尚未成交的委托（包括限价单和停止单）
        for orderID in self.orderList:
            self.cancelOrder(orderID)
        self.orderList = []

        # 计算指标数值
        self.barList.append(bar)
        
        if len(self.barList) <= 2:
            return
        else:
            self.barList.pop(0)
        lastBar = self.barList[-2]
        
        # 新的一天
        if lastBar.datetime.date() != bar.datetime.date():
            # 如果已经初始化
            if self.dayHigh:
                self.range = self.dayHigh - self.dayLow
                self.longEntry = bar.open + self.k1 * self.range
                self.shortEntry = bar.open - self.k2 * self.range           
                
            self.dayOpen = bar.open
            self.dayHigh = bar.high
            self.dayLow = bar.low

            self.longEntered = False
            self.shortEntered = False
        else:
            self.dayHigh = max(self.dayHigh, bar.high)
            self.dayLow = min(self.dayLow, bar.low)

        # 尚未到收盘
        if not self.range:
            return

        if bar.datetime.time() < self.exitTime:
            if self.pos == 0:
                if bar.close > self.dayOpen:
                    if not self.longEntered:
                        vtOrderID = self.buy(self.longEntry, self.fixedSize, stop=True)
                        self.orderList.append(vtOrderID)
                else:
                    if not self.shortEntered:
                        vtOrderID = self.short(self.shortEntry, self.fixedSize, stop=True)
                        self.orderList.append(vtOrderID)
    
            # 持有多头仓位
            elif self.pos > 0:
                self.longEntered = True

                # 多头止损单
                vtOrderID = self.sell(self.shortEntry, self.fixedSize, stop=True)
                self.orderList.append(vtOrderID)
                
                # 空头开仓单
                if not self.shortEntered:
                    vtOrderID = self.short(self.shortEntry, self.fixedSize, stop=True)
                    self.orderList.append(vtOrderID)
                
            # 持有空头仓位
            elif self.pos < 0:
                self.shortEntered = True

                # 空头止损单
                vtOrderID = self.cover(self.longEntry, self.fixedSize, stop=True)
                self.orderList.append(vtOrderID)
                
                # 多头开仓单
                if not self.longEntered:
                    vtOrderID = self.buy(self.longEntry, self.fixedSize, stop=True)
                    self.orderList.append(vtOrderID)  
            
        # 收盘平仓
        else:
            if self.pos > 0:
                vtOrderID = self.sell(bar.close * 0.99, abs(self.pos))
                self.orderList.append(vtOrderID)
            elif self.pos < 0:
                vtOrderID = self.cover(bar.close * 1.01, abs(self.pos))
                self.orderList.append(vtOrderID) 
 
        # 发出状态更新事件
        self.putEvent()

    #----------------------------------------------------------------------
    def onOrder(self, order):
        """收到委托变化推送（必须由用户继承实现）"""
        pass

    #----------------------------------------------------------------------
    def onTrade(self, trade):
        # 发出状态更新事件
        self.putEvent()
