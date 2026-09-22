"""Install an unenergized programmable TX filter in either comparison chip."""
from tx_reconstruction import Reconstruction

def reconstructed(base,kind):
 class Reconstructed(base):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)
        self.tx.set_reconstruction(Reconstruction(kind))
    def reference_metrics(self):
        r=super().reference_metrics();r['tx_reconstruction']=self.tx.reconstruction.metrics();return r
 return Reconstructed
