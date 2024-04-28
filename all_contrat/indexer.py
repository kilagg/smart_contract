from algosdk.v2client.algod import AlgodClient
from algosdk.v2client.indexer import IndexerClient
from base64 import b64decode


FEES_ADDRESS = '3FXLFER4JF4SPVBSSTPZWGTFUYSD54QOEZ4Y4TV4ZTRHERT2Z6DH7Q54YQ'
algod_token_tx = ""
headers_tx = {"X-Algo-API-Token": algod_token_tx}
client = AlgodClient(
    algod_token=algod_token_tx,
    algod_address="https://testnet-api.voi.nodly.io:443",
    headers=headers_tx,
)


def get_app_global_state(app_id: int):
    app_nfo = client.application_info(app_id)
    state = dict()
    for pair in app_nfo["params"]["global-state"]:
        key = b64decode(pair["key"])

        value = pair["value"]
        value_type = value["type"]

        if value_type == 2:
            # value is uint64
            value = value.get("uint", 0)
        elif value_type == 1:
            # value is byte array
            value = b64decode(value.get("bytes", ""))
        else:
            raise Exception(f"Unexpected state type: {value_type}")
        state[key] = value
    return state


indexer_client = IndexerClient(
    indexer_token="",
    indexer_address="https://testnet-idx.voi.nodly.io",
    headers={"X-Algo-API-Token": ""}
)
chain = 'voi:testnet'


round = 6446566
round = 6448448 # create 1/72
round = 6447176 # buy 1/72
round = 6447461 # update 1/72
round = 6447883 # cancel 1/72
round = 6448094 # update 200/72
round = 6448146 # cancel 200/72
round = 6448206 # buy 200/72
round = 6448343 # update voi / rwa
round = 6448381 # close voi / rwa
round = 6448417 # buy voi rwa
round = 6448480 # update arc200 rwa
round = 6448533 # close arc200 rwa
round = 6448566 # buy arc200 rwa
round = 6448671 # close dutch voi 72
round = 6448811 # buy dutch voi 72
round = 6448957 # close dutch arc200 72
round = 6449122 # dutch buy arc200 72

round = 6448448
print(indexer_client.search_transactions_by_address(FEES_ADDRESS, round_num=round)['transactions'])
print("ok")
print(indexer_client.search_transactions_by_address(FEES_ADDRESS, round_num=round)['transactions'][0])

for transaction in indexer_client.search_transactions_by_address(FEES_ADDRESS, round_num=round)['transactions']:
    if 'application-transaction' in transaction and 'inner-txns' in transaction:
        application_id = transaction['application-transaction']['application-id']
        sender = transaction['sender']
        round_time = transaction['round-time']
        tx_id = transaction['id']
        app_args = transaction['application-transaction']['application-args']
        inner_txns = [tx for tx in transaction['inner-txns']
                      if 'note' in tx and 'tx-type' in tx and tx['payment-transaction']['receiver'] == FEES_ADDRESS]
        if len(inner_txns) == 1:
            note = b64decode(inner_txns[0]['note']).decode('ascii')
            type_tx = note.split(",")[0]
            action_tx = note.split(",")[1]
            currency_tx = note.split(",")[2]
            if type_tx == 'sale':
                if currency_tx == '1/72':
                    if action_tx == 'fund':
                        price = get_app_global_state(application_id)[b'price']
                        new_data = {
                            'id': tx_id,
                            'created_at': round_time,
                            'from_address': sender,
                            'chain': chain,
                            'app_id': application_id,
                            'type': 'create',
                            'amount': price,
                            'currency': 0,
                            'note': note
                        }
                        print(new_data)
                    if action_tx == 'update':
                        price = int.from_bytes(b64decode(app_args[1]), byteorder='big')
                        new_data = {
                            'id': tx_id,
                            'created_at': round_time,
                            'from_address': sender,
                            'chain': chain,
                            'app_id': application_id,
                            'type': 'update',
                            'amount': price,
                            'currency': 0,
                            'note': note
                        }
                        print(new_data)
                    if action_tx == 'buy':
                        price = transaction['inner-txns'][1]['payment-transaction']['amount']
                        new_data = {
                            'id': tx_id,
                            'created_at': round_time,
                            'from_address': sender,
                            'chain': chain,
                            'app_id': application_id,
                            'type': 'buy',
                            'amount': price,
                            'currency': 0,
                            'note': note
                        }
                        print(new_data)
                    if action_tx == 'close':
                        new_data = {
                            'id': tx_id,
                            'created_at': round_time,
                            'from_address': sender,
                            'chain': chain,
                            'app_id': application_id,
                            'type': 'cancel',
                            'amount': None,
                            'currency': None,
                            'note': note
                        }
                        print(new_data)
                if currency_tx == '200/72':
                    if action_tx == 'update':
                        price = int.from_bytes(b64decode(app_args[1]), byteorder='big')
                        currency = get_app_global_state(application_id)[b"arc200_app_id"]
                        new_data = {
                            'id': tx_id,
                            'created_at': round_time,
                            'from_address': sender,
                            'chain': chain,
                            'app_id': application_id,
                            'type': 'update',
                            'amount': price,
                            'currency': currency,
                            'note': note
                        }
                        print(new_data)
                    elif action_tx == 'buy':
                        currency = transaction['inner-txns'][2]['application-transaction']['application-id']
                        price = int.from_bytes(b64decode(transaction['inner-txns'][2]['application-transaction']['application-args'][2]), byteorder='big')
                        new_data = {
                            'id': tx_id,
                            'created_at': round_time,
                            'from_address': sender,
                            'chain': chain,
                            'app_id': application_id,
                            'type': 'buy',
                            'amount': price,
                            'currency': currency,
                            'note': note
                        }
                        print(new_data)
                    elif action_tx == 'close':
                        new_data = {
                            'id': tx_id,
                            'created_at': round_time,
                            'from_address': sender,
                            'chain': chain,
                            'app_id': application_id,
                            'type': 'cancel',
                            'amount': None,
                            'currency': None,
                            'note': note
                        }
                        print(new_data)
                if currency_tx == '1/rwa':
                    if action_tx == 'update':
                        price = int.from_bytes(b64decode(app_args[1]), byteorder='big')
                        new_data = {
                            'id': tx_id,
                            'created_at': round_time,
                            'from_address': sender,
                            'chain': chain,
                            'app_id': application_id,
                            'type': 'update',
                            'amount': price,
                            'currency': 0,
                            'note': note
                        }
                        print(new_data)
                    elif action_tx == 'buy':
                        price = transaction['inner-txns'][0]['payment-transaction']['amount']
                        new_data = {
                            'id': tx_id,
                            'created_at': round_time,
                            'from_address': sender,
                            'chain': chain,
                            'app_id': application_id,
                            'type': 'buy',
                            'amount': price,
                            'currency': 0,
                            'note': note
                        }
                        print(new_data)
                    elif action_tx == 'close':
                        new_data = {
                            'id': tx_id,
                            'created_at': round_time,
                            'from_address': sender,
                            'chain': chain,
                            'app_id': application_id,
                            'type': 'cancel',
                            'amount': None,
                            'currency': None,
                            'note': note
                        }
                        print(new_data)
                if currency_tx == '200/rwa':
                    if action_tx == 'update':
                        currency = get_app_global_state(application_id)[b"arc200_app_id"]
                        price = int.from_bytes(b64decode(app_args[1]), byteorder='big')
                        new_data = {
                            'id': tx_id,
                            'created_at': round_time,
                            'from_address': sender,
                            'chain': chain,
                            'app_id': application_id,
                            'type': 'update',
                            'amount': price,
                            'currency': currency,
                            'note': note
                        }
                        print(new_data)
                    elif action_tx == 'close':
                        new_data = {
                            'id': tx_id,
                            'created_at': round_time,
                            'from_address': sender,
                            'chain': chain,
                            'app_id': application_id,
                            'type': 'cancel',
                            'amount': None,
                            'currency': None,
                            'note': note
                        }
                        print(new_data)
                    elif action_tx == 'buy':
                        price = int.from_bytes(b64decode(transaction['inner-txns'][1]['application-transaction']['application-args'][2]), byteorder='big')
                        currency = transaction['inner-txns'][1]['application-transaction']['application-id']
                        new_data = {
                            'id': tx_id,
                            'created_at': round_time,
                            'from_address': sender,
                            'chain': chain,
                            'app_id': application_id,
                            'type': type_tx,
                            'amount': price,
                            'currency': currency,
                            'note': note
                        }
                        print(new_data)
            if type_tx == 'dutch':
                if currency_tx == '1/72':
                    if action_tx == 'buy':
                        price = transaction['inner-txns'][0]['payment-transaction']['amount']
                        new_data = {
                            'id': tx_id,
                            'created_at': round_time,
                            'from_address': sender,
                            'chain': chain,
                            'app_id': application_id,
                            'type': 'buy',
                            'amount': price,
                            'currency': 0,
                            'note': note
                        }
                        print(new_data)
                    elif action_tx == 'close':
                        new_data = {
                            'id': tx_id,
                            'created_at': round_time,
                            'from_address': sender,
                            'chain': chain,
                            'app_id': application_id,
                            'type': 'cancel',
                            'amount': None,
                            'currency': None,
                            'note': note
                        }
                        print(new_data)
                if currency_tx == '200/72':
                    if action_tx == 'buy':
                        price = int.from_bytes(b64decode(app_args[1]), byteorder='big')
                        currency = transaction['inner-txns'][1]['application-transaction']['application-id']
                        new_data = {
                            'id': tx_id,
                            'created_at': round_time,
                            'from_address': sender,
                            'chain': chain,
                            'app_id': application_id,
                            'type': 'buy',
                            'amount': '??',
                            'currency': currency,
                            'note': note
                        }
                        print(new_data)
                    if action_tx == 'close':
                        new_data = {
                            'id': tx_id,
                            'created_at': round_time,
                            'from_address': sender,
                            'chain': chain,
                            'app_id': application_id,
                            'type': 'cancel',
                            'amount': None,
                            'currency': None,
                            'note': note
                        }
                        print(new_data)
