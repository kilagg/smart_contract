from pyteal import *

def approval_program():
    # PARAMETERS
    seller_key = Bytes("seller")
    nft_id_key = Bytes("nft_id")
    nft_app_id_key = Bytes("nft_app_id")
    nft_price = Bytes("price")
    start_time_key = Bytes("start")
    arc200_app_id_key =  Bytes("arc200_app_id") # New parameter for ARC-200 asset ID

    @Subroutine(TealType.none)
    def transferNFT(to_account: Expr) -> Expr:
        return Seq(
                InnerTxnBuilder.Begin(),
                InnerTxnBuilder.SetFields({
                    TxnField.type_enum: TxnType.ApplicationCall,
                    TxnField.application_id: App.globalGet(nft_app_id_key), 
                    TxnField.accounts: [to_account, Global.current_application_address()],
                    TxnField.on_completion: OnComplete.NoOp,
                    TxnField.applications: [App.globalGet(nft_app_id_key)],
                    TxnField.application_args: [
                        Bytes("arc72_transferFrom"),
                        Global.current_application_address(),
                        to_account,  # Assuming to_account is already a byte array
                        Itob(App.globalGet(nft_id_key))  # Assuming this returns a byte array or is converted appropriately
                    ],
                }),
                InnerTxnBuilder.Submit(),
            )

        
    ##############################################################################################
    @Subroutine(TealType.none)
    def FetchApprovedARC200ToEscrow(owner: Expr, amount: Expr) -> Expr:
        return Seq(
            # Make sure this contract is Opted in to the ARC200 before trying to transferFrom
            # Opt-in to the payment token (ARC200) to be able to have a sale balance (if ARC200 is implemented like that?)
            InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields({
                TxnField.type_enum: TxnType.ApplicationCall,
                TxnField.application_id: App.globalGet(arc200_app_id_key),
                TxnField.applications: [App.globalGet(arc200_app_id_key)],
                TxnField.accounts: [Gtxn[1].accounts[0], Gtxn[1].accounts[1], Global.current_application_address()],
                TxnField.on_completion: OnComplete.OptIn,
            }),
            InnerTxnBuilder.Submit(),
            # Fetch the tokens we have been promised/approved

            InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields({
                TxnField.type_enum: TxnType.ApplicationCall,
                TxnField.application_id: App.globalGet(arc200_app_id_key),
                TxnField.applications: [App.globalGet(arc200_app_id_key)],
                TxnField.accounts: [Gtxn[1].accounts[0], Gtxn[1].accounts[1], Global.current_application_address()],
                TxnField.application_args: [
                    Bytes("arc200_transferFrom"),
                    owner,
                    Global.current_application_address(),
                    Itob(amount)
                ],
            }),
            InnerTxnBuilder.Submit(),   
        )

    @Subroutine(TealType.none)
    def SendARC200ToSeller(amount: Expr) -> Expr:
        return Seq(
            InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields({
                TxnField.type_enum: TxnType.ApplicationCall,
                TxnField.application_id: App.globalGet(arc200_app_id_key),
                TxnField.accounts: [Gtxn[1].accounts[0], Gtxn[1].accounts[1],Global.current_application_address()],
                TxnField.applications: [App.globalGet(arc200_app_id_key)],
                TxnField.application_args: [
                    Bytes("arc200_transfer"),
                    App.globalGet(seller_key),
                    Itob(amount)
                ],
                TxnField.on_completion: OnComplete.NoOp
            }),
            InnerTxnBuilder.Submit(),
        )
        
    ################################################################################################################################################
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

    @Subroutine(TealType.uint64)
    def allowance_check(owner: Expr) -> Expr:
        return Seq(
            InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields({
                TxnField.type_enum: TxnType.ApplicationCall,
                TxnField.application_id: App.globalGet(arc200_app_id_key),
                TxnField.applications: [App.globalGet(arc200_app_id_key)],
                TxnField.accounts: [Gtxn[1].accounts[0], Gtxn[1].accounts[1], Global.current_application_address()],
                TxnField.application_args: [
                    Bytes("arc200_allowance"),              # // method
                    owner,                                  # // allower
                    Global.current_application_address()    # // spendee
                ],
            }),
            InnerTxnBuilder.Submit(),
            Return(InnerTxn.last_valid())
        )

    @Subroutine(TealType.bytes)
    def arc72_owner(tokenId: Expr) -> Expr:
        return Seq(
            InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields({
                TxnField.type_enum: TxnType.ApplicationCall,
                TxnField.application_id: App.globalGet(nft_app_id_key),
                TxnField.applications: [App.globalGet(arc200_app_id_key), App.globalGet(nft_app_id_key)],
                TxnField.accounts: [Global.current_application_address()],
                TxnField.application_args: [
                    Bytes("arc72_ownerOf"),              # // method
                    tokenId                              # // tokenId
                ],
            }),
            InnerTxnBuilder.Submit(),
            Return(InnerTxn.last_log())
        )

    ################################################################################################################################################
    @Subroutine(TealType.none)
    def clear_state_from_app() -> Expr:
        return Seq([
            InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields({
                TxnField.type_enum: TxnType.ApplicationCall,
                TxnField.application_id: App.globalGet(arc200_app_id_key),
                TxnField.applications: [App.globalGet(arc200_app_id_key), App.globalGet(nft_app_id_key)],
                TxnField.accounts: [Global.current_application_address()],
                TxnField.on_completion: OnComplete.ClearState,  # Opt-out of the ARC200 contract
            }),
            InnerTxnBuilder.Submit(),
        ])
        

    ################################################################################################################################################
    # VARIABLE SETUP
    note_content = Bytes("This is a note field")

    on_create_start_time = Btoi(Txn.application_args[3])
    on_create = Seq(
        App.globalPut(seller_key, Txn.application_args[0]),
        App.globalPut(nft_app_id_key, Btoi(Txn.application_args[1])),
        App.globalPut(nft_id_key, Btoi(Txn.application_args[2])),
        App.globalPut(start_time_key, on_create_start_time),
        App.globalPut(nft_price, Btoi(Txn.application_args[4])),
        App.globalPut(arc200_app_id_key, Btoi(Txn.application_args[5])),
        Approve(),
    )

    ##############################################################################################################################
    on_buy = Seq(
        Assert(
            allowance_check(Txn.sender()) >= App.globalGet(nft_price)
        ),
        Seq(
            # Fetch nft_price arc200 tokens on the escrow sale contract from buyer
            FetchApprovedARC200ToEscrow(Txn.sender(), App.globalGet(nft_price)),
            # transfer these back to the seller
            SendARC200ToSeller(App.globalGet(nft_price)),
            # transfer NFT to buyer
            transferNFT(Txn.sender()),
            Approve()
        ),
        Reject(),
    )

    ################################################################################################################################################
    new_price = Btoi(Txn.application_args[1])
    on_update_price = Seq(
        Assert(
            Or(
                # sender must either be the seller or the Sale creator
                Txn.sender() == App.globalGet(seller_key),
                Txn.sender() == Global.creator_address()
            )
        ),
        Assert( new_price > Int(0) ),
        ## UPDATE NEW PRICE
        App.globalPut(nft_price, new_price),
        Approve()
    )

    #######################
    ################################################################################################################################################
    #######################
    
    on_call_method = Txn.application_args[0]
    on_call = Cond(
        [on_call_method == Bytes("buy"), on_buy],
        [on_call_method == Bytes("update_price"), on_update_price]
    )

    
    # Logic to clear specific local state entries related to the ARC200 app
    clear_logic = Seq([
        # Example: Delete local state entries related to ARC200 interactions
        # Adjust the key names based on your actual use case
        App.localDel(Txn.sender(), Bytes("balance")),
        Return(Int(1))
    ])

    on_delete = Seq(
        Assert(
            Or(
                # sender must either be the seller or the Sale creator
                Txn.sender() == App.globalGet(seller_key),
                Txn.sender() == Global.creator_address()
            )
        ),
        # Check if current app is opted into ARC200 app
        If(App.optedIn(Global.current_application_address(), App.globalGet(arc200_app_id_key))).Then(
            clear_state_from_app()
        ),
        If(
            arc72_owner(Itob(App.globalGet(nft_id_key))) ==  Global.current_application_address()
        ).
        Then(
            transferNFT(App.globalGet(seller_key))
        ),
        # send remaining funds to the seller
        closeAccountTo(App.globalGet(seller_key)),
        Approve(),
    )


    #######################
    ################################################################################################################################################
    #######################

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
    with open("approval.teal", "w") as f:
        compiled = compileTeal(approval_program(), mode=Mode.Application, version=9)
        f.write(compiled)

    with open("clear_state.teal", "w") as f:
        compiled = compileTeal(clear_state_program(), mode=Mode.Application, version=9)
        f.write(compiled)
