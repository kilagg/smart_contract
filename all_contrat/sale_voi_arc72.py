from pyteal import *
from all_contrat.constants import FEES_ADDRESS, FEES


def approval_program():
    # PARAMETERS
    nft_id_key = Bytes("nft_id")
    nft_app_id_key = Bytes("nft_app_id")
    nft_price = Bytes("price")
    fees_address = Bytes("fees_address")

    @Subroutine(TealType.none)
    def function_transfert_nft(to_account: Expr) -> Expr:
        return Seq(
            InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields({
                TxnField.type_enum: TxnType.ApplicationCall,
                TxnField.application_id: App.globalGet(nft_app_id_key),
                TxnField.on_completion: OnComplete.NoOp,
                TxnField.application_args: [
                    Bytes("base16", "f2f194a0"),
                    Global.creator_address(),
                    to_account,
                    App.globalGet(nft_id_key)
                ],
            }),
            InnerTxnBuilder.Submit(),
        )

    @Subroutine(TealType.none)
    def function_pay_seller() -> Expr:
        return Seq(
            InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields(
                {
                    TxnField.type_enum: TxnType.Payment,
                    TxnField.amount: App.globalGet(nft_price)-Int(FEES),
                    TxnField.sender: Global.current_application_address(),
                    TxnField.receiver: Global.creator_address(),
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
        App.globalPut(nft_app_id_key, Btoi(Txn.application_args[0])),
        App.globalPut(nft_id_key, Txn.application_args[1]),
        App.globalPut(nft_price, Btoi(Txn.application_args[2])),
        App.globalPut(fees_address, Txn.application_args[3]),
        Approve(),
    )

    on_buy = Seq(
        Assert(
            And(
                Gtxn[Txn.group_index() - Int(1)].amount() == App.globalGet(nft_price),
                Gtxn[Txn.group_index() - Int(1)].receiver() == Global.current_application_address(),
                Gtxn[Txn.group_index() - Int(1)].type_enum() == TxnType.Payment,
                Gtxn[Txn.group_index() - Int(1)].sender() == Txn.sender(),
            )
        ),
        Seq(
            function_send_note(Int(0), Bytes("sale,buy,1/72")),
            function_pay_seller(),
            function_transfert_nft(Gtxn[Txn.group_index() - Int(1)].sender()),
            function_close_app(),
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
            function_send_note(Int(0), Bytes("sale,update,1/72")),
            App.globalPut(nft_price, Btoi(Txn.application_args[1])),
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
        Assert(
            Txn.sender() == Global.creator_address()
        ),
        function_send_note(Int(0), Bytes("sale,close,1/72")),
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

    with open("algo_arc72_sale_approval.teal", "w") as f:
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
        f.write(compiled)
