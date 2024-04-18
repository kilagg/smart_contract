from pyteal import *


def approval_program():
    # PARAMETERS
    seller_key = Bytes("seller")
    price = Bytes("price")
    fees_address = Bytes("fees_address")
    name = Bytes("name")
    description = Bytes("description")

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
        App.globalPut(price, Btoi(Txn.application_args[1])),
        App.globalPut(fees_address, Txn.application_args[2]),
        App.globalPut(name, Txn.application_args[3]),
        App.globalPut(description, Txn.application_args[4]),
        Approve(),
    )

    on_buy_txn_index = Txn.group_index() - Int(1)
    on_buy = Seq(
        Assert(
            And(
                Gtxn[on_buy_txn_index].amount() == Itob(App.globalGet(price)),
                Gtxn[on_buy_txn_index].receiver() == Global.current_application_address(),
                Gtxn[on_buy_txn_index].type_enum() == TxnType.Payment,
                Gtxn[on_buy_txn_index].sender() == Txn.sender(),
            )
        ),
        Seq(
            SendNoteToFees(Int(0), Bytes("sale,buy,1/rwa")),
            SendAlgoToSeller(Gtxn[on_buy_txn_index].amount()-Int(0)),
            Approve()
        ),
        Reject(),
    )

    new_price = Btoi(Txn.application_args[1])
    on_update_price = Seq(
        Assert(
            Or(
                Txn.sender() == App.globalGet(seller_key),
                Txn.sender() == Global.creator_address()
            )
        ),
        Assert(new_price > Int(0)),
        Seq(
            App.globalPut(price, new_price),
            SendNoteToFees(Int(0), Bytes("sale,update,1/rwa")),
            Approve()
        ),
        Reject()
    )

    on_call_method = Txn.application_args[0]
    on_call = Cond(
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
        SendNoteToFees(Int(0), Bytes("sale,close,1/rwa")),
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


if __name__ == "__main__":

    with open("algo_rwa_sale_approval.teal", "w") as f:
        compiled = compileTeal(approval_program(), mode=Mode.Application, version=10)
        f.write(compiled)