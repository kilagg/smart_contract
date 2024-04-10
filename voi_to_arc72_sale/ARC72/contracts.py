from pyteal import *

def approval_program():
    # PARAMETERS
    owner_key = Bytes("owner")  # Owner of the NFT
    nft_id_key = Bytes("nft_id")  # Unique identifier for the NFT
    
    # Utility function to check if the sender is the owner of the NFT
    @Subroutine(TealType.uint64)
    def is_owner(sender: Expr) -> Expr:
        return sender == App.globalGet(owner_key)
    
    # ARC-72 methods
    # arc72_ownerOf implementation
    @Subroutine(TealType.bytes)
    def ownerOf() -> Expr:
        token_id = Btoi(Txn.application_args[1])
        Assert(token_id == App.globalGet(nft_id_key))
        return App.globalGet(owner_key)
    
    # arc72_transferFrom implementation  
    @Subroutine(TealType.none)
    def transferFrom(from_addr: Expr, to_addr: Expr, token_id: Expr) -> Expr:
        return Seq([
            Assert(token_id == App.globalGet(nft_id_key)),
            Assert(from_addr == App.globalGet(owner_key)),
            App.globalPut(owner_key, to_addr),
            Log(Concat(Bytes("arc72_Transfer("), 
                       from_addr, Bytes(","), 
                       to_addr, Bytes(","), 
                       Itob(token_id), Bytes(")"))),
        ])

    # # arc72_transferFrom implementation  
    # @Subroutine(TealType.none)
    # def transfer(to_addr: Expr, token_id: Expr) -> Expr:
    #     return Seq([
    #         Assert(token_id == App.globalGet(nft_id_key)),
    #         Assert(Txn.sender() == App.globalGet(owner_key)),
    #         App.globalPut(owner_key, to_addr),
    #         Log(Concat(Bytes("arc72_Transfer("), 
    #                    Txn.sender(), Bytes(","), 
    #                    to_addr, Bytes(","), 
    #                    Itob(token_id), Bytes(")"))),
    #     ])
    
    # On creation, set the creator as the owner and store the NFT ID
    on_creation = Seq([
        App.globalPut(owner_key, Txn.sender()),
        App.globalPut(nft_id_key, Btoi(Txn.application_args[0])),
        Approve()
    ])
    
    on_call_method = Txn.application_args[0]
    on_call = Cond(
        [on_call_method == Bytes("arc72_transferFrom"), 
            Seq(        
                transferFrom(
                    Txn.application_args[1], 
                    Txn.application_args[2],
                    Btoi(Txn.application_args[3])),
            Approve()
            )
        ]
    )
    
    # Program start
    program = Cond(
        [Txn.application_id() == Int(0), on_creation]
        ,
        [Txn.on_completion() == OnComplete.NoOp, on_call]
    )
    
    return program

def clear_state_program():
    return Approve()

if __name__ == "__main__":
    with open("arc72_approval.teal", "w") as f:
        compiled = compileTeal(approval_program(), mode=Mode.Application, version=5)
        f.write(compiled)

    with open("arc72_clear_state.teal", "w") as f:
        compiled = compileTeal(clear_state_program(), mode=Mode.Application, version=5)
        f.write(compiled)
