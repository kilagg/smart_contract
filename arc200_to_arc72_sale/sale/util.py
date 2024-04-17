from typing import List, Tuple, Dict, Any, Optional, Union
from base64 import b64decode

from algosdk.v2client.algod import AlgodClient
from algosdk import encoding

from pyteal import compileTeal, Mode, Expr

from .account import Account


import base64
from hashlib import sha512

# Function to convert bytes to a base32-like encoded string with checksum, inspired by Algorand's address format
def to_algorand_address_style(byte_data):
    # Encode the byte data to base32
    encoded = base64.b32encode(byte_data).decode('utf-8').rstrip('=')

    # Calculate checksum: SHA512_256 of the encoded data, take last 4 bytes, then base32 encode
    checksum = sha512(byte_data).digest()[-4:]
    checksum_encoded = base64.b32encode(checksum).decode('utf-8').rstrip('=')

    # Combine encoded data with checksum
    address = encoded + checksum_encoded
    return address

class PendingTxnResponse:
    def __init__(self, response: Dict[str, Any]) -> None:
        self.poolError: str = response["pool-error"]
        self.txn: Dict[str, Any] = response["txn"]

        self.applicationIndex: Optional[int] = response.get("application-index")
        self.assetIndex: Optional[int] = response.get("asset-index")
        self.closeRewards: Optional[int] = response.get("close-rewards")
        self.closingAmount: Optional[int] = response.get("closing-amount")
        self.confirmedRound: Optional[int] = response.get("confirmed-round")
        self.globalStateDelta: Optional[Any] = response.get("global-state-delta")
        self.localStateDelta: Optional[Any] = response.get("local-state-delta")
        self.receiverRewards: Optional[int] = response.get("receiver-rewards")
        self.senderRewards: Optional[int] = response.get("sender-rewards")

        self.innerTxns: List[Any] = response.get("inner-txns", [])
        self.logs: List[bytes] = [b64decode(l) for l in response.get("logs", [])]


def waitForTransaction(
    client: AlgodClient, txID: str, timeout: int = 10
) -> PendingTxnResponse:
    lastStatus = client.status()
    lastRound = lastStatus["last-round"]
    startRound = lastRound

    while lastRound < startRound + timeout:
        pending_txn = client.pending_transaction_info(txID)

        if pending_txn.get("confirmed-round", 0) > 0:
            return PendingTxnResponse(pending_txn)

        if pending_txn["pool-error"]:
            raise Exception("Pool error: {}".format(pending_txn["pool-error"]))

        lastStatus = client.status_after_block(lastRound + 1)

        lastRound += 1

    raise Exception(
        "Transaction {} not confirmed after {} rounds".format(txID, timeout)
    )


def fullyCompileContract(client: AlgodClient, contract: Expr) -> bytes:
    teal = compileTeal(contract, mode=Mode.Application, version=10)
    response = client.compile(teal)
    return b64decode(response["result"])


def decodeState(stateArray: List[Any]) -> Dict[bytes, Union[int, bytes]]:
    state: Dict[bytes, Union[int, bytes]] = dict()

    for pair in stateArray:
        key = b64decode(pair["key"])

        value = pair["value"]
        valueType = value["type"]

        if valueType == 2:
            # value is uint64
            value = value.get("uint", 0)
        elif valueType == 1:
            # value is byte array
            value = b64decode(value.get("bytes", ""))
        else:
            raise Exception(f"Unexpected state type: {valueType}")

        state[key] = value

    return state


def getAppGlobalState(
    client: AlgodClient, appID: int
) -> Dict[bytes, Union[int, bytes]]:
    appInfo = client.application_info(appID)
    return decodeState(appInfo["params"]["global-state"])


def getAppLocalState(client: AlgodClient, appID: int, account: str) -> Dict[bytes, Union[int, bytes]]:
    """
    Fetches the local state for a given account and application ID.

    Args:
        client (AlgodClient): An instance of the Algod client.
        appID (int): The application ID.
        account (str): The account address whose local state you want to fetch.

    Returns:
        Dict[bytes, Union[int, bytes]]: The local state of the account for the given app.
    """
    account_info = client.account_info(account.getAddress())
    local_state = next(
        (app['key-value'] for app in account_info.get('apps-local-state', [])
         if app['id'] == appID),
        []
    )
    return decodeState(local_state)

def getBalances(client: AlgodClient, account: str) -> Dict[int, int]:
    balances: Dict[int, int] = dict()

    accountInfo = client.account_info(account)

    # set key 0 to Algo balance
    balances[0] = accountInfo["amount"]

    assets: List[Dict[str, Any]] = accountInfo.get("assets", [])
    for assetHolding in assets:
        assetID = assetHolding["asset-id"]
        amount = assetHolding["amount"]
        balances[assetID] = amount

    return balances


def getLastBlockTimestamp(client: AlgodClient) -> Tuple[int, int]:
    status = client.status()
    lastRound = status["last-round"]
    block = client.block_info(lastRound)
    timestamp = block["block"]["ts"]

    return block, timestamp
