from pyteal import *
from all_contrat.constants import FEES_ADDRESS, FEES


def approval_program():
    # PARAMETERS
    nft_id_key = Bytes("nft_id")
    nft_app_id_key = Bytes("nft_app_id")
    fees_address = Bytes("fees_address")
    end_time_key = Bytes("end")
    late_bid_delay_key = Bytes("late_bid_delay")
    lead_bid_account_key = Bytes("bid_account")
    reserve_amount_key = Bytes("reserve_amount")
    lead_bid_amount_key = Bytes("bid_amount")

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

    @Subroutine(TealType.none)
    def repayPreviousLeadBidder() -> Expr:
        return Seq(
            InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields(
                {
                    TxnField.type_enum: TxnType.Payment,
                    TxnField.amount: App.globalGet(lead_bid_amount_key) - Global.min_txn_fee(),
                    TxnField.receiver: App.globalGet(lead_bid_account_key),
                }
            ),
            InnerTxnBuilder.Submit(),
        )

    @Subroutine(TealType.bytes)
    def arc72_owner() -> Expr:
        return Seq(
            InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields(
                {
                    TxnField.type_enum: TxnType.ApplicationCall,
                    TxnField.application_id: App.globalGet(nft_app_id_key),
                    TxnField.applications: [
                        App.globalGet(nft_app_id_key),
                    ],
                    TxnField.accounts: [Global.current_application_address()],
                    TxnField.application_args: [
                        Bytes("base16", "79096a14"),  # arc72_OwnerOf
                        App.globalGet(nft_id_key),  # arg: tokenId
                    ],
                }
            ),
            InnerTxnBuilder.Submit(),
            Return(InnerTxn.last_log()),
        )

    on_create = Seq(
        App.globalPut(nft_app_id_key, Btoi(Txn.application_args[0])),
        App.globalPut(nft_id_key, Txn.application_args[1]),
        App.globalPut(reserve_amount_key, Btoi(Txn.application_args[2])),
        App.globalPut(fees_address, Txn.application_args[3]),
        App.globalPut(end_time_key, Btoi(Txn.application_args[4])),
        App.globalPut(lead_bid_account_key, Global.zero_address()),
        App.globalPut(late_bid_delay_key, Int(600)),
        App.globalPut(lead_bid_amount_key, Int(0)),
        Approve(),
    )

    on_bid = Seq(
        Assert(
            And(
                Global.latest_timestamp() < App.globalGet(end_time_key),
                Gtxn[Txn.group_index() - Int(1)].type_enum() == TxnType.Payment,
                Gtxn[Txn.group_index() - Int(1)].receiver() == Global.current_application_address(),
                Gtxn[Txn.group_index() - Int(1)].amount() >= App.globalGet(reserve_amount_key),
                Gtxn[Txn.group_index() - Int(1)].amount() >= Div(Mul(App.globalGet(lead_bid_amount_key), Int(110)), Int(100))
            )
        ),
        Seq(
            If(
                App.globalGet(lead_bid_account_key) != Global.zero_address()
            ).Then(
                repayPreviousLeadBidder()
            ),
            function_send_note(Int(0), Bytes("auction,bid,1/72")),
            App.globalPut(lead_bid_amount_key, Gtxn[Txn.group_index() - Int(1)].amount()),
            App.globalPut(lead_bid_account_key, Gtxn[Txn.group_index() - Int(1)].sender()),
            If(
                Global.latest_timestamp() + App.globalGet(late_bid_delay_key) >= App.globalGet(end_time_key)
            ).Then(
                App.globalPut(end_time_key, (Global.latest_timestamp() + App.globalGet(late_bid_delay_key)))
            ),
            Approve(),
        )
    )

    on_delete = Seq(
        If(
            App.globalGet(lead_bid_account_key) == Global.zero_address()
        ).Then(
            Seq(
                Assert(
                    Or(
                        Txn.sender() == Global.creator_address(),
                        App.globalGet(end_time_key) <= Global.latest_timestamp()
                    )
                ),
                function_send_note(Int(0), Bytes("auction,close_none,1/72")),
                function_close_app(),
                Approve(),
            )
        ).Else(
            If(
                App.globalGet(end_time_key) <= Global.latest_timestamp()
            ).Then(
                Seq(
                    If(
                        arc72_owner() == Global.creator_address()
                    ).Then(
                        Seq(
                            function_send_note(Int(0), Bytes("auction,close_buy,1/72")),
                            function_transfert_nft(App.globalGet(lead_bid_account_key))
                        )
                    ).Else(
                        function_send_note(Int(0), Bytes("auction,close_none,1/72")),
                        repayPreviousLeadBidder()
                    ),
                    function_close_app(),
                    Approve(),
                )
            ),
        ),
        Reject(),
    )

    program = Cond(
        [Txn.application_id() == Int(0), on_create],
        [And(Txn.on_completion() == OnComplete.NoOp, Txn.application_args[0] == Bytes("bid")), on_bid],
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
