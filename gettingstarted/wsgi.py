"""
WSGI config for gettingstarted project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/2.1/howto/deployment/wsgi/
"""

# import os
#
# os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gettingstarted.settings")
#
# from django.core.wsgi import get_wsgi_application
#
# application = get_wsgi_application()

from flask import Flask, request, json
import ccxt
import pprint

api_key = "R19apmpdek5DXoCEshvxg3yEVLCxoF5SfGM42QLntHFuLVnz3qFxw5yrKtqeDwX0"
secret = "SxCJoYL2Xi2LHsuCZRzBfWA8Go1uS3JgeZ4eFSkbN1EvOoMggTOUisTclqfMVRbh"

app = Flask(__name__)

@app.route('/')
def index():
    return 'Hello, Flask!'

@app.route('/webhook', methods = ['POST'])
def webhook():

    symbol1 = "BTCUSDT"
    symbol2 = "BTC/USDT"

    data = json.loads(request.data)
    # pprint.pprint(data['order'] )
    # return 'Hello, webhook!'

    # binance 객체 생성
    binance = ccxt.binance(config={
        'apiKey': api_key,
        'secret': secret,
        'enableRateLimit': True,
        'options': {
            'defaultType': 'future'
        }
    })

    # //USDS-M 선물 잔고를 조회
    balance = binance.fetch_balance(params={"type": "future"})
    # balance..set_position_mode(hedged=True, symbol=symbol2)
    positions = balance['info']['positions']
    positionAmt = 0
    # leverage = 0
    for position in positions:
        if position["symbol"] == symbol1:
            # pprint.pprint(position)
            positionAmt = float(position['positionAmt'])
            leverage = float(position['leverage'])

    # 현금보유액
    cash = float(balance['USDT']['free'])
    # 현재가격조회
    price1 = binance.fetch_ticker(symbol2)
    price2 = float(price1['last'])

    # 주문가능수량
    qty = (cash/price2) * (leverage - 0.5)

    # //트레이딩뷰 해석
    order = data['order']
    orders = [None] * 3

    # 보유포지션이 없는경우
    if float(positionAmt) == 0:
        if order == "buy":
            # 매수/롱 포지션 진입
            orders[0] = binance.create_order(
                symbol=symbol2,
                type="MARKET",
                side="buy",
                amount=qty
            )
        else:
            # 매도/숏 포지션 진입
            orders[0] = binance.create_order(
                symbol=symbol2,
                type="MARKET",
                side="sell",
                amount=qty
            )
    # 포지션 보유중인 경우
    else:
        if order == "buy":
            # 숏 포지션 보유중인 경우 숏포지션 정리후 롱포지션 진입
            if float(positionAmt) < 0.0:
                orders[0] = binance.create_order(
                    symbol=symbol2,
                    type="MARKET",
                    side="buy",
                    amount=qty
                )
                orders[0] = binance.create_order(
                    symbol=symbol2,
                    type="MARKET",
                    side="buy",
                    amount=qty
                )
        else:
            # 롱 포지션 보유중인 경우 롱포지션 정리후 숏포지션 진입
            if float(positionAmt) > 0.0:
                orders[0] = binance.create_order(
                    symbol=symbol2,
                    type="MARKET",
                    side="sell",
                    amount=qty
                )
                orders[0] = binance.create_order(
                    symbol=symbol2,
                    type="MARKET",
                    side="sell",
                    amount=qty
                )

    for order in orders:
        pprint.pprint(order)

    # # //시장가 주문과TP / SL
    # orders = [None] * 3
    #
    # # market price (ex: 19500$)
    # orders[0] = binance.create_order(
    #     symbol="BTC/USDT",
    #     type="MARKET",
    #     side="buy",
    #     amount=0.001
    # )
    #
    # # take profit
    # orders[1] = binance.create_order(
    #     symbol="BTC/USDT",
    #     type="TAKE_PROFIT_MARKET",
    #     side="sell",
    #     amount=0.001,
    #     params={'stopPrice': 19700}
    # )
    #
    # # stop loss
    # orders[2] = binance.create_order(
    #     symbol="BTC/USDT",
    #     type="STOP_MARKET",
    #     side="sell",
    #     amount=0.001,
    #     params={'stopPrice': 19300}
    # )
    #
    # for order in orders:
    #     pprint.pprint(order)


if __name__ == '__main__':
    app.run(debug=True)