import string

from flask import Flask, request, json
import ccxt
import pprint

app = Flask(__name__)

# 실행환경 0:로컬 / 1:heroku서버
process = 0

@app.route('/')
def index():
    pprint.pprint(1-(int('3')/100))

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
    stopPer = data['stopPer']
    # 거래대상 코인
    symbol = data['ticker'][0:len(data['ticker']) - 4] + "/" + data['ticker'][-4:]
    # 롱포자션 손절퍼센트 설정
    longStopPrice = 1-(int(stopPer)/100)
    # 숏포자션 손절퍼센트 설정
    shortStopPrice = 1+(int(stopPer)/100)
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
            pprint.pprint(position)
            # 현재 설정되어있는 레버라지 취득
            leverage = float(position['leverage'])

    # 현재가격조회
    current_price = float(binance.fetch_ticker(symbol)['last'])
    pprint.pprint(current_price)
    # 구입가능현금보유액
    cash = 0.0
    free = float(balance['USDT']['free']) / 4
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


    # 산규주문가능수량
    qty = (cash/current_price) * (leverage)
    #############################################

    # 보유포지션이 없는경우 신규주문
    if float(positionAmt) == 0:
        if orderType == "buy":
            # 매수/롱 포지션 진입
            binance.create_order(
                symbol=symbol,
                type="MARKET",
                side="buy",
                amount=qty
            )
            # stop loss 설정
            binance.create_order(
                symbol=symbol,
                type="STOP_MARKET",
                side="sell",
                amount=qty,
                params={'stopPrice': current_price * longStopPrice}
            )
        if orderType == "sell":
            # 매도/숏 포지션 진입
            binance.create_order(
                symbol=symbol,
                type="MARKET",
                side="sell",
                amount=qty
            )
            # stop loss 설정
            binance.create_order(
                symbol=symbol,
                type="STOP_MARKET",
                side="buy",
                amount=qty,
                params={'stopPrice': current_price * shortStopPrice}
            )
    # 포지션 보유중인 경우
    else:
        open_order = binance.fetch_open_orders(symbol=symbol)
        order_id = open_order[0]['info']['orderId']
        if orderType == "buy":
            if float(positionAmt) < 0.0:
                # 현재 보유중인 포지션의 stop loss 주문 취소
                binance.cancel_order(
                    id=order_id,
                    symbol=symbol
                )
                # 현재 보유중인 숏포지션 정리 & 신규 롱포지션 진입
                binance.create_order(
                    symbol=symbol,
                    type="MARKET",
                    side="buy",
                    amount=(-positionAmt) + qty
                )
                # 신규 롱포지션 stop loss 설정
                binance.create_order(
                    symbol=symbol,
                    type="STOP_MARKET",
                    side="sell",
                    amount=qty,
                    params={'stopPrice': current_price * longStopPrice}
                )
            else:
                # 현재 보유중인 롱포지션 정리
                binance.create_order(
                    symbol=symbol,
                    type="MARKET",
                    side="sell",
                    amount=positionAmt
                )
        if orderType == "sell":
            if float(positionAmt) > 0.0:
                # 현재 보유중인 포지션의 stop loss 주문 취소
                binance.cancel_order(
                    id=order_id,
                    symbol=symbol
                )
                # 현재 보유중인 롱포지션 정리 & 신규 숏포지션 진입
                binance.create_order(
                    symbol=symbol,
                    type="MARKET",
                    side="sell",
                    amount=positionAmt + qty
                )
                # 신규 숏포지션 stop loss 설정
                binance.create_order(
                    symbol=symbol,
                    type="STOP_MARKET",
                    side="buy",
                    amount=qty,
                    params={'stopPrice': current_price * shortStopPrice}
                )
            else:
                # 현재 보유중인 숏포지션 정리
                binance.create_order(
                    symbol=symbol,
                    type="MARKET",
                    side="buy",
                    amount=(-positionAmt)
                )


if __name__ == '__main__':
    app.run(debug=True)