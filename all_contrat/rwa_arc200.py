from pyteal import *
from all_contrat.constants import FEES_ADDRESS, FEES


def approval_program():
    # PARAMETERS
    arc200_app_id_key = Bytes("arc200_app_id")
    arc200_app_address = Bytes("arc200_app_address")
    price = Bytes("price")
    fees_address = Bytes("fees_address")
    name = Bytes("name")
    description = Bytes("description")

    @Subroutine(TealType.none)
    def function_arc200_fund() -> Expr:
        return Seq(
            InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields(
                {
                    TxnField.type_enum: TxnType.Payment,
                    TxnField.amount: Int(28500),
                    TxnField.sender: Global.current_application_address(),
                    TxnField.receiver: App.globalGet(arc200_app_address)
                }
            ),
            InnerTxnBuilder.Submit(),
        )

    @Subroutine(TealType.none)
    def function_arc200_transfer() -> Expr:
        return Seq(
            InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields(
                {
                    TxnField.type_enum: TxnType.ApplicationCall,
                    TxnField.application_id: App.globalGet(arc200_app_id_key),
                    TxnField.on_completion: OnComplete.NoOp,
                    TxnField.application_args: [
                        Bytes("base16", "da7025b9"),
                        Global.creator_address(),
                        App.globalGet(price)
                    ]
                }
            ),
            InnerTxnBuilder.Submit(),
        )

    @Subroutine(TealType.none)
    def function_send_note(amount: Expr, note: Expr) -> Expr:
        return Seq(
            InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields(
                {
                    TxnField.type_enum: TxnType.Payment,
                    TxnField.amount: amount,
                    TxnField.sender: Global.current_application_address(),
                    TxnField.receiver: App.globalGet(fees_address),
                    TxnField.note: note,
                }
            ),
            InnerTxnBuilder.Submit(),
        )

    @Subroutine(TealType.none)
    def function_close_app() -> Expr:
        return If(Balance(Global.current_application_address()) != Int(0)).Then(
            Seq(
                InnerTxnBuilder.Begin(),
                InnerTxnBuilder.SetFields(
                    {
                        TxnField.type_enum: TxnType.Payment,
                        TxnField.close_remainder_to: Global.creator_address(),
                    }
                ),
                InnerTxnBuilder.Submit(),
            )
        )

    on_create = Seq(
        App.globalPut(price, Txn.application_args[0]),
        App.globalPut(fees_address, Txn.application_args[1]),
        App.globalPut(name, Txn.application_args[2]),
        App.globalPut(description, Txn.application_args[3]),
        App.globalPut(arc200_app_id_key, Btoi(Txn.application_args[4])),
        App.globalPut(arc200_app_address, Txn.application_args[5]),
        Approve(),
    )

    on_buy = Seq(
        Seq(
            function_arc200_fund(),
            function_arc200_transfer(),
            function_send_note(Int(0), Bytes("sale,buy,200/rwa")),
            Approve()
        ),
        Reject(),
    )

    on_update_price = Seq(
        Assert(
            And(
                Txn.sender() == Global.creator_address(),
                Btoi(Txn.application_args[1]) > Int(0)
            )
        ),
        Seq(
            function_send_note(Int(0), Bytes("sale,update,200/rwa")),
            App.globalPut(price, Btoi(Txn.application_args[1])),
            Approve()
        ),
        Reject()
    )

    on_call = Cond(
        [Txn.application_args[0] == Bytes("pre_validate"), Approve()],
        [Txn.application_args[0] == Bytes("buy"), on_buy],
        [Txn.application_args[0] == Bytes("update_price"), on_update_price]
    )

    on_delete = Seq(
        Assert(Txn.sender() == Global.creator_address()),
        function_send_note(Int(0), Bytes("sale,close,200/rwa")),
        function_close_app(),
        Approve(),
    )

    program = Cond(
        [Txn.application_id() == Int(0), on_create],
        [Txn.on_completion() == OnComplete.NoOp, on_call],
        [Txn.on_completion() == OnComplete.DeleteApplication, on_delete],
        [
            Or(
                Txn.on_completion() == OnComplete.OptIn,
                Txn.on_completion() == OnComplete.CloseOut,
                Txn.on_completion() == OnComplete.UpdateApplication,
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
    print("ended")