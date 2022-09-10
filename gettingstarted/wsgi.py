import string

from flask import Flask, request, json
import ccxt
import pprint

app = Flask(__name__)

@app.route('/')
def index():
    return 'Hello, Flask!'

@app.route('/webhook', methods = ['POST'])
def webhook():

    with open("../binance-apiKey.txt") as f:
        lines = f.readlines()
        api_key = lines[0].strip()
        secret = lines[1].strip()

    # binance 객체 생성
    binance = ccxt.binance(config={
        'apiKey': api_key,
        'secret': secret,
        'enableRateLimit': True,
        'options': {
            'defaultType': 'future'
        }
    })

    # 트레이딩뷰에서 보내온 알림해석
    data = json.loads(request.data)
    orderType = data['order']
    symbol = data['ticker'][0:len(data['ticker']) - 4] + "/" + data['ticker'][-4:]

    # 바이낸스에 USDS-M 선물 잔고조회
    balance = binance.fetch_balance(params={"type": "future"})
    positions = balance['info']['positions']
    positionAmt = 0.0
    leverage = 0

    for position in positions:
        if position["symbol"] == data['ticker']:
            positionAmt = float(position['positionAmt'])
            # 현재 설정되어있는 레버라지 취득
            leverage = float(position['leverage'])

    # 구입가능현금보유액
    cash = float(balance['USDT']['free'])
    # 현재가격조회
    current_price = float(binance.fetch_ticker(symbol)['last'])
    # 주문가능수량
    qty = (cash/current_price) * (leverage - 0.5)
    # 롱포자션 손절퍼센트 설정
    longStopPrice = 0.98
    # 숏포자션 손절퍼센트 설정
    shortStopPrice = 1.02

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
            # stop loss
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
            # stop loss
            binance.create_order(
                symbol=symbol,
                type="STOP_MARKET",
                side="buy",
                amount=qty,
                params={'stopPrice': current_price * shortStopPrice}
            )
    # 포지션 보유중인 경우
    else:
        if orderType == "buy":
            # 숏 포지션 보유중인 경우 숏포지션 정리후 롱포지션 진입
            if float(positionAmt) < 0.0:
                # 매도/숏 포지션 정리
                binance.create_order(
                    symbol=symbol,
                    type="MARKET",
                    side="buy",
                    amount=qty
                )
                # 매도/숏 포지션 진입
                binance.create_order(
                    symbol=symbol,
                    type="MARKET",
                    side="buy",
                    amount=qty
                )
                # stop loss
                binance.create_order(
                    symbol=symbol,
                    type="STOP_MARKET",
                    side="sell",
                    amount=qty,
                    params={'stopPrice': current_price * longStopPrice}
                )
        if orderType == "sell":
            # 롱 포지션 보유중인 경우 롱포지션 정리후 숏포지션 진입
            if float(positionAmt) > 0.0:
                # 매수/롱 포지션 정리
                binance.create_order(
                    symbol=symbol,
                    type="MARKET",
                    side="sell",
                    amount=qty
                )
                # 매수/롱 포지션 진입
                binance.create_order(
                    symbol=symbol,
                    type="MARKET",
                    side="sell",
                    amount=qty
                )
                # stop loss
                binance.create_order(
                    symbol=symbol,
                    type="STOP_MARKET",
                    side="buy",
                    amount=qty,
                    params={'stopPrice': current_price * shortStopPrice}
                )

if __name__ == '__main__':
    app.run(debug=True)