"""Second attempt: band-limited level (subtract 120 s moving mean, then 2 s moving mean), decimated x10 on both,
normalised sliding xcorr of every Fig2A channel against every F2B column (decimation 1 assumed: both 10 Hz)."""
import numpy as np, scipy.io as sio
from scipy.signal import fftconvolve
from scipy.ndimage import uniform_filter1d
R='C:/Users/mmebr/Documents/CNN/'
P=sio.loadmat(R+'DATA/raw/F2B.mat')['F2B']
def band(x): x=np.asarray(x,float); x=x-uniform_filter1d(x,1200); return uniform_filter1d(x,20)[::10]
B=[band(P[:,c]) for c in range(5)]
for ch in range(5):
    a=band(np.load(R+f'DATA/derived/channels/Fig2A_dt0p1/CH{ch}.npy',mmap_mode='r'))
    a=(a-a.mean())/a.std(); n=len(a); best=None
    for col in range(5):
        db=B[col]; num=fftconvolve(db,a[::-1],mode='valid')
        c1=np.cumsum(np.r_[0,db]); c2=np.cumsum(np.r_[0,db*db]); s=c1[n:]-c1[:-n]; ss=c2[n:]-c2[:-n]
        r=num/(n*np.sqrt(np.maximum(ss/n-(s/n)**2,1e-30))); i=int(np.nanargmax(np.abs(r)))
        if best is None or abs(r[i])>abs(best[2]): best=(col,i*10,r[i])
    print(f'Fig2A CH{ch}: best F2B col {best[0]} row ~{best[1]} (t={best[1]/36000:.2f} h at 10 Hz) r={best[2]:.3f}',flush=True)
