import ethereum
import icontract


class Contract(icontract.IContract):
    def setup(self, web3_contract):
        self.web3.deposit(web3_contract, self.contract_address, 50000000000000000)

    def has_been_hacked(self):
        contract_bal = ethereum.EasyWeb3().balance(self.contract_address)
        if int(contract_bal) < 50000000000000000:
            return True
        else:
            return False
