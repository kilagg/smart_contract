from pyteal import *


def approval_program():
    # PARAMETERS
    seller_key = Bytes("seller")
    nft_id_key = Bytes("nft_id")
    nft_app_id_key = Bytes("nft_app_id")
    nft_price = Bytes("price")
    fees_address = Bytes("fees_address")

    @Subroutine(TealType.none)
    def transferNFT(to_account: Expr) -> Expr:
        return Seq(
            InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields({
                TxnField.type_enum: TxnType.ApplicationCall,
                TxnField.application_id: App.globalGet(nft_app_id_key),
                TxnField.on_completion: OnComplete.NoOp,
                TxnField.application_args: [
                    Bytes("base16", "f2f194a0"),
                    App.globalGet(seller_key),
                    to_account,
                    App.globalGet(nft_id_key)
                ],
            }),
            InnerTxnBuilder.Submit(),
        )

    @Subroutine(TealType.none)
    def SendAlgoToSeller(amount: Expr) -> Expr:
        return Seq(
            InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields(
                {
                    TxnField.type_enum: TxnType.Payment,
                    TxnField.amount: amount,
                    TxnField.sender: Global.current_application_address(),
                    TxnField.receiver: App.globalGet(seller_key),
                }
            ),
            InnerTxnBuilder.Submit(),
        )

    @Subroutine(TealType.none)
    def SendNoteToFees(amount: Expr, note: Expr) -> Expr:
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
    def closeAccountTo(account: Expr) -> Expr:
        return If(Balance(Global.current_application_address()) != Int(0)).Then(
            Seq(
                InnerTxnBuilder.Begin(),
                InnerTxnBuilder.SetFields(
                    {
                        TxnField.type_enum: TxnType.Payment,
                        TxnField.close_remainder_to: account,
                    }
                ),
                InnerTxnBuilder.Submit(),
            )
        )

    on_create = Seq(
        App.globalPut(seller_key, Txn.application_args[0]),
        App.globalPut(nft_app_id_key, Btoi(Txn.application_args[1])),
        App.globalPut(nft_id_key, Txn.application_args[2]),
        App.globalPut(nft_price, Btoi(Txn.application_args[3])),
        App.globalPut(fees_address, Txn.application_args[4]),
        Approve(),
    )

    on_buy_txn_index = Txn.group_index() - Int(1)
    on_buy = Seq(
        Assert(
            And(
                Gtxn[on_buy_txn_index].amount() == App.globalGet(nft_price),
                Gtxn[on_buy_txn_index].receiver() == Global.current_application_address(),
                Gtxn[on_buy_txn_index].type_enum() == TxnType.Payment,
                Gtxn[on_buy_txn_index].sender() == Txn.sender(),
            )
        ),
        Seq(
            SendNoteToFees(Int(0), Bytes("sale,buy,1/72")),
            SendAlgoToSeller(Gtxn[on_buy_txn_index].amount()-Int(0)),  # pay seller immediately
            transferNFT(
                Gtxn[on_buy_txn_index].sender()), # send the NFT to the seller.
            Approve()
        ),
        Reject(),
    )

    new_price = Btoi(Txn.application_args[1])
    on_update_price = Seq(
        Assert(
            And(
                Txn.sender() == App.globalGet(seller_key),
                new_price > Int(0)
            )
        ),
        Seq(
            App.globalPut(nft_price, new_price),
            SendNoteToFees(Int(0), Bytes("sale,update,1/72")),
            Approve()
        ),
        Reject()
    )

    on_call_method = Txn.application_args[0]
    on_call = Cond(
        [on_call_method == Bytes("pre_validate"), Approve()],
        [on_call_method == Bytes("buy"), on_buy],
        [on_call_method == Bytes("update_price"), on_update_price]
    )

    on_delete = Seq(
        Assert(
            Or(
                Txn.sender() == App.globalGet(seller_key),
                Txn.sender() == Global.creator_address()
            )
        ),
        SendNoteToFees(Int(0), Bytes("sale,close,1/72")),
        closeAccountTo(App.globalGet(seller_key)),
        Approve(),
    )

    program = Cond(
        [Txn.application_id() == Int(0), on_create],
        [Txn.on_completion() == OnComplete.NoOp, on_call],
        [
            Txn.on_completion() == OnComplete.DeleteApplication,
            on_delete,
        ],
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


def clear_state_program():
    return Approve()


if __name__ == "__main__":

    with open("algo_arc72_sale_approval.teal", "w") as f:
        compiled = compileTeal(approval_program(), mode=Mode.Application, version=10)
        f.write(compiled)

    with open("algo_arc72_sale_clear_state.teal", "w") as f:
        compiled = compileTeal(clear_state_program(), mode=Mode.Application, version=10)
        f.write(compiled)