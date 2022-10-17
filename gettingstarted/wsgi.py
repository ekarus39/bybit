
from flask import Flask, request, json
from pybit import HTTP
import ccxt

app = Flask(__name__)

# 실행환경 0:로컬 / 1:heroku서버
process = 1

@app.route('/')
def index():
   return 'Hello, Flask!'

@app.route('/webhook', methods = ['POST'])
def webhook():

    # API key ###################################
    if process == 0:
        # 로컬파일패스
        with open("../binance-apiKey.txt") as f:
            lines = f.readlines()
            apiKey = lines[0].strip()
            secret = lines[1].strip()
    else:
        # heroku
        with open("binance-apiKey.txt") as f:
            lines = f.readlines()
            apiKey = lines[0].strip()
            secret = lines[1].strip()

    # binance 객체 생성
    binance = ccxt.binance(config={
        'apiKey': apiKey,
        'secret': secret,
        'enableRateLimit': True,
        'options': {
            'defaultType': 'future'
        }
    })
    #############################################


    # 트레이딩뷰에서 보내온 알림해석 #################
    data = json.loads(request.data)
    # 매수/매도
    orderType = data['order']
    # 매수 한계금액
    seed = float(data['seed'])
    # 손절 퍼센트
    lossPer = data['lossPer']
    # 익절 퍼센트
    profitPer = data['profitPer']
    # comment
    comment = data['comment']

    # 거래대상 코인
    symbol = data['ticker'][0:len(data['ticker']) - 4] + "/" + data['ticker'][-4:]

    # 손절퍼센트 설정
    lossPerPrice = 0.0
    # 익절퍼센트 설정
    profitPerPrice = 0.0

    if orderType == 'buy':
        lossPerPrice = 1 - (float(lossPer) / 100)
        profitPerPrice = 1 + (float(profitPer) / 100)
    if orderType == 'sell':
        lossPerPrice = 1 + (float(lossPer) / 100)
        profitPerPrice = 1 - (float(profitPer) / 100)
    #############################################

    # 바이낸스에 USDS-M 선물 잔고조회 ###############
    balance = binance.fetch_balance(params={"type": "future"})
    positions = balance['info']['positions']
    # 보유포지션
    positionAmt = 0.0
    leverage = 0

    for position in positions:
        if position["symbol"] == data['ticker']:
            positionAmt = float(position['positionAmt'])
            # pprint.pprint(position)

            # 현재가격조회
            current_price = float(binance.fetch_ticker(symbol)['last'])
            # 구입가능현금보유액
            cash = 0
            # 현재 설정되어있는 레버라지 취득
            leverage = float(position['leverage'])

    free = float(balance['USDT']['free'])
    if seed == 0:
        cash = free
    else:
        if positionAmt == 0:
            if free > seed:
                cash = seed
            else:
                cash = free
        else:
            if positionAmt < 0:
                if seed > free + (-positionAmt * current_price):
                    cash = free + (-positionAmt * current_price)
                else:
                    cash = seed
            else:
                if seed > free + (positionAmt * current_price):
                    cash = free + (positionAmt * current_price)
                else:
                    cash = seed


    # 신규주문가능수량
    qty = (cash/current_price) * (leverage)
    if qty < 1:
        qty = str(qty)[0:5]
    else:
        qty = round(qty)
    ############################################

    if orderType == "buy":
        if float(positionAmt) < 0.0:
            open_order = binance.fetch_open_orders(symbol=symbol)
            for order_id in open_order:
                # 현재 보유중인 포지션의 stop loss 주문 취소
                binance.cancel_order(
                    id=order_id['info']['orderId'],
                    symbol=symbol
                )
            # 현재 보유중인 숏포지션 정리 &
            binance.create_order(
                symbol=symbol,
                type="MARKET",
                side="buy",
                amount=(-positionAmt)
            )

        balance = binance.fetch_balance(params={"type": "future"})
        free = float(balance['USDT']['free'])
        # 구입가능현금보유액 계산
        cash = 0.0
        if free > seed:
            cash = seed
        else:
            cash = free-5
        # 산규주문가능수량
        qty = (cash / current_price) * (leverage)
        if qty < 1:
            qty = str(qty)[0:5]
        else:
            qty = round(qty)

        # 신규 롱포지션 진입
        if comment == "Long Only":
            binance.create_order(
                symbol=symbol,
                type="MARKET",
                side="buy",
                amount=qty
            )
            # 신규 롱포지션 stop loss 설정
            binance.create_order(
                symbol=symbol,
                type="STOP_MARKET",
                side="sell",
                amount=qty,
                params={'stopPrice': current_price * lossPerPrice}
            )
            # take profit 설정
            binance.create_order(
                symbol=symbol,
                type="TAKE_PROFIT_MARKET",
                side="sell",
                amount=qty,
                params={'stopPrice': current_price * profitPerPrice}
            )
    if orderType == "sell":
        if float(positionAmt) > 0.0:
            open_order = binance.fetch_open_orders(symbol=symbol)
            for order_id in open_order:
                # 현재 보유중인 포지션의 stop loss 주문 취소
                binance.cancel_order(
                    id=order_id,
                    symbol=symbol
                )
            # 현재 보유중인 롱포지션 정리
            binance.create_order(
                symbol=symbol,
                type="MARKET",
                side="sell",
                amount=positionAmt
            )

        balance = binance.fetch_balance(params={"type": "future"})
        free = float(balance['USDT']['free'])
        # 구입가능현금보유액 계산
        cash = 0.0
        if free > seed:
            cash = seed
        else:
            cash = free-5
        # 산규주문가능수량
        qty = (cash / current_price) * (leverage)
        if qty < 1:
            qty = str(qty)[0:5]
        else:
            qty = round(qty)

        # 신규 숏포지션 진입
        if comment == "Short Only":
            binance.create_order(
                symbol=symbol,
                type="MARKET",
                side="sell",
                amount=qty
            )
            # 신규 숏포지션 stop loss 설정
            binance.create_order(
                symbol=symbol,
                type="STOP_MARKET",
                side="buy",
                amount=qty,
                params={'stopPrice': current_price * lossPerPrice}
            )
            # take profit 설정
            binance.create_order(
                symbol=symbol,
                type="TAKE_PROFIT_MARKET",
                side="buy",
                amount=qty,
                params={'stopPrice': current_price * profitPerPrice}
            )


@app.route('/webhook/bybit', methods = ['POST'])
def webhook_bybit():

    # API key ###################################
    if process == 0:
        # 로컬파일패스
        with open("../bybit-apiKey.txt") as f:
            lines = f.readlines()
            apiKey = lines[0].strip()
            secret = lines[1].strip()
    else:
        # heroku
        with open("bybit-apiKey.txt") as f:
            lines = f.readlines()
            apiKey = lines[0].strip()
            secret = lines[1].strip()

    # bybit 객체 생성
    exchange = HTTP(
        endpoint="https://api.bybit.com",
        api_key=apiKey,
        api_secret=secret
    )
    #############################################

    # 트레이딩뷰에서 보내온 알림해석 #################
    data = json.loads(request.data)
    # 매수/매도
    orderType = data['order']
    # 매수 한계금액
    seed = float(data['seed'])
    # 손절 퍼센트
    lossPer = data['lossPer']
    # 익절 퍼센트
    profitPer = data['profitPer']
    # comment
    comment = data['comment']

    # 거래대상 코인
    symbol = data['ticker'][0:len(data['ticker']) - 4] + data['ticker'][-4:]
    #############################################

    # USDT 잔고조회
    free = float(exchange.get_wallet_balance(coin="USDT")['result']['USDT']['available_balance'])
    # 보유COIN 조회
    positions = exchange.my_position(symbol=symbol)['result']

    # 구입가능현금보유액 계산
    cash = 0.0
    if free > seed:
        cash = seed
    else:
        cash = free

    buyLeverage = 0.0
    sellLeverage = 0.0

    # 현재가격조회
    current_buy_price = float(exchange.latest_information_for_symbol(symbol=symbol)['result'][0]['ask_price'])
    current_sell_price = float(exchange.latest_information_for_symbol(symbol=symbol)['result'][0]['bid_price'])

    # 손절퍼센트 설정
    lossPerPrice = 0.0
    # 익절퍼센트 설정
    profitPerPrice = 0.0

    if orderType == 'buy':
        lossPerPrice = 1 - (float(lossPer) / 100)
        profitPerPrice = 1 + (float(profitPer) / 100)
    if orderType == 'sell':
        lossPerPrice = 1 + (float(lossPer) / 100)
        profitPerPrice = 1 - (float(profitPer) / 100)

    # 보유포지션
    posQt = 0
    for position in positions:
        if position["side"] == 'Buy':
            buyLeverage = position["leverage"]
            if position["size"] != 0:
                posQt = position["size"]
        if position["side"] == 'Sell':
            sellLeverage = position["leverage"]
            if position["size"] != 0:
                posQt = position["size"]

    if orderType == "buy":
        # 산규주문가능수량 계산
        qty = ((cash / current_buy_price) * (buyLeverage))
        if qty < 1:
            qty = str(qty)[0:5]
        else:
            qty = round(qty)

        if posQt > 0:
            # 보유포지션 청산
            exchange.place_active_order(
                symbol=symbol,
                side='Buy',
                order_type="Market",
                qty=posQt,
                time_in_force="GoodTillCancel",
                reduce_only=True,
                close_on_trigger=True,
            )
        if comment == "Long Only":
            # 매수/롱 포지션 진입
            lossprice = str(current_buy_price * lossPerPrice)
            profitprice = str(current_buy_price * profitPerPrice)
            print(profitprice[0:len(str(current_buy_price))])
            resp = exchange.place_active_order(
                symbol=symbol,
                side="Buy",
                order_type="Market",
                qty=qty,
                time_in_force="GoodTillCancel",
                reduce_only=False,
                close_on_trigger=False,
                take_profit=profitprice[0:len(str(current_buy_price))],
                stop_loss=lossprice[0:len(str(current_buy_price))]
            )

    if orderType == "sell":
        # 산규주문가능수량 계산
        qty = ((cash / current_sell_price) * (sellLeverage))
        if qty < 1:
            qty = str(qty)[0:5]
        else:
            qty = round(qty)

        if posQt > 0:
             # 보유포지션 청산
            exchange.place_active_order(
                symbol=symbol,
                side='Sell',
                order_type="Market",
                qty=posQt,
                time_in_force="GoodTillCancel",
                reduce_only=True,
                close_on_trigger=True,
            )
        if comment == "Short Only":
            # 매도/숏 포지션 진입
            lossprice = str(current_sell_price * lossPerPrice)
            profitprice = str(current_sell_price * profitPerPrice)

            exchange.place_active_order(
                symbol=symbol,
                side="Sell",
                order_type="Market",
                qty=qty,
                time_in_force="GoodTillCancel",
                reduce_only=False,
                close_on_trigger=False,
                take_profit=profitprice[0:len(str(current_sell_price))],
                stop_loss=lossprice[0:len(str(current_sell_price))]

            )



if __name__ == '__main__':
    app.run(debug=True)