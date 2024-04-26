from pyteal import *
from all_contrat.constants import FEES_ADDRESS, FEES


def approval_program():
    # PARAMETERS
    nft_id_key = Bytes("nft_id")
    nft_app_id_key = Bytes("nft_app_id")
    arc200_app_id_key = Bytes("arc200_app_id")
    nft_max_price = Bytes("max_price")
    nft_min_price = Bytes("min_price")
    fees_address = Bytes("fees_address")
    start_time_key = Bytes("start")
    end_time_key = Bytes("end")
    nft_app_address = Bytes("nft_app_address")

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
    def function_arc200_fund() -> Expr:
        return Seq(
            InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields(
                {
                    TxnField.type_enum: TxnType.Payment,
                    TxnField.amount: Int(28500),
                    TxnField.sender: Global.current_application_address(),
                    TxnField.receiver: App.globalGet(nft_app_address)
                }
            ),
            InnerTxnBuilder.Submit(),
        )

    @Subroutine(TealType.none)
    def function_arc200_transfer(amount) -> Expr:
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
                        App.globalGet(amount)
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
        App.globalPut(nft_app_id_key, Btoi(Txn.application_args[0])),
        App.globalPut(arc200_app_id_key, Btoi(Txn.application_args[1])),
        App.globalPut(nft_id_key, Txn.application_args[2]),
        App.globalPut(nft_max_price, Btoi(Txn.application_args[3])),
        App.globalPut(nft_min_price, Btoi(Txn.application_args[4])),
        App.globalPut(fees_address, Txn.application_args[5]),
        App.globalPut(nft_app_address, Btoi(Txn.application_args[6])),
        App.globalPut(end_time_key, Btoi(Txn.application_args[7])),
        App.globalPut(start_time_key, Global.latest_timestamp()),
        Assert(App.globalGet(nft_max_price) >= App.globalGet(nft_min_price)),
        Assert(App.globalGet(end_time_key) > App.globalGet(start_time_key)),
        Approve(),
    )

    on_buy = Seq(
        Assert(
            And(
                # formula to compute price is y = (((max-min)/(start-end)) * (current_time - start )) + max
                # new formula : max - (current-start)((max-min)/(end-start))
                Btoi(Txn.application_args[1]) >= Minus(
                    App.globalGet(nft_max_price),
                    Mul(
                        Minus(
                            Global.latest_timestamp(),
                            App.globalGet(start_time_key)
                        ),
                        Div(
                            Minus(
                                App.globalGet(nft_max_price),
                                App.globalGet(nft_min_price)
                            ),
                            Minus(
                                App.globalGet(end_time_key),
                                App.globalGet(start_time_key)
                            )
                        )
                    )
                ),
                Global.latest_timestamp() <= App.globalGet(end_time_key),
                Gtxn[Txn.group_index() - Int(1)].receiver() == Global.current_application_address(),
                Gtxn[Txn.group_index() - Int(1)].type_enum() == TxnType.Payment,
                Gtxn[Txn.group_index() - Int(1)].sender() == Txn.sender()
            )
        ),
        Seq(
            function_send_note(Int(FEES), Bytes("dutch,buy,200/72")),
            function_arc200_fund(),
            function_arc200_transfer(Btoi(Txn.application_args[1])),
            function_transfert_nft(Txn.sender()),
            Approve()
        ),
        Reject()
    )

    on_call = Cond(
        [Txn.application_args[0] == Bytes("pre_validate"), Approve()],
        [Txn.application_args[0] == Bytes("buy"), on_buy]
    )

    on_delete = Seq(
        Assert(
            Txn.sender() == Global.creator_address()
        ),
        function_send_note(Int(FEES), Bytes("dutch,close,200/72")),
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
                Txn.on_completion() == OnComplete.CloseOut
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
