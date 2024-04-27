from pyteal import *
from all_contrat.constants import FEES_ADDRESS, PURCHASE_FEES
from all_contrat.subroutine import fees_address, price
from all_contrat.subroutine import function_send_note, function_close_app
from all_contrat.subroutine import on_update, on_fund, on_delete


def approval_program():
    name = Bytes("name")
    description = Bytes("description")

    @Subroutine(TealType.none)
    def function_payment() -> Expr:
        return Seq(
            InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields(
                {
                    TxnField.type_enum: TxnType.Payment,
                    TxnField.amount: App.globalGet(price)-Int(PURCHASE_FEES),
                    TxnField.sender: Global.current_application_address(),
                    TxnField.receiver: Global.creator_address(),
                }
            ),
            InnerTxnBuilder.Submit(),
        )

    on_create = Seq(
        App.globalPut(price, Btoi(Txn.application_args[0])),
        App.globalPut(name, Txn.application_args[1]),
        App.globalPut(description, Txn.application_args[2]),
        App.globalPut(fees_address, Addr(FEES_ADDRESS)),
        Approve(),
    )

    on_buy = Seq(
        Assert(
            And(
                Gtxn[Txn.group_index() - Int(1)].amount() == App.globalGet(price),
                Gtxn[Txn.group_index() - Int(1)].receiver() == Global.current_application_address(),
                Gtxn[Txn.group_index() - Int(1)].type_enum() == TxnType.Payment,
                Gtxn[Txn.group_index() - Int(1)].sender() == Txn.sender()
            )
        ),
        Seq(
            function_payment(),
            function_send_note(Int(PURCHASE_FEES), Bytes("sale,buy,1/rwa")),
            function_close_app(),
            Approve()
        ),
        Reject()
    )

    program = Cond(
        [Txn.application_id() == Int(0), on_create],
        [Txn.on_completion() == OnComplete.DeleteApplication, on_delete("sale,close,1/rwa")],
        [And(Txn.on_completion() == OnComplete.NoOp, Txn.application_args[0] == Bytes("fund")), on_fund("sale,fund,1/rwa")],
        [And(Txn.on_completion() == OnComplete.NoOp, Txn.application_args[0] == Bytes("update_price")), on_update("sale,update,1/rwa")],
        [And(Txn.on_completion() == OnComplete.NoOp, Txn.application_args[0] == Bytes("buy")), on_buy],
        [
            Or(
                Txn.on_completion() == OnComplete.OptIn,
                Txn.on_completion() == OnComplete.CloseOut,
                Txn.on_completion() == OnComplete.UpdateApplication
            ),
            Reject(),
        ],
    )

    return program


if __name__ == "__main__":
    compiled = compileTeal(approval_program(), mode=Mode.Application, version=10)
    from algosdk.v2client.algod import AlgodClient

    algod_token_tx = ""
    headers_tx = {"X-Algo-API-Token": algod_token_tx}
    client = AlgodClient(
        algod_token=algod_token_tx,
        algod_address="https://testnet-api.voi.nodly.io:443",
        headers=headers_tx,
    )
    print(client.compile(compiled)['result'])
