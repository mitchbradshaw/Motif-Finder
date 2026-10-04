"""Read-only: is Fig2A_dt0p1 an excerpt of DATA/raw/F2B.mat (5 x 5,184,001, 10 Hz if 6 days)?
Slides the first difference of each Fig2A channel along each F2B column (FFT normalised xcorr)."""
import numpy as np, scipy.io as sio
from scipy.signal import fftconvolve
R='C:/Users/mmebr/Documents/CNN/'
P=sio.loadmat(R+'DATA/raw/F2B.mat')['F2B']
out=[]
for ch in range(5):
    a=np.load(R+f'DATA/derived/channels/Fig2A_dt0p1/CH{ch}.npy',mmap_mode='r')
    da=np.diff(np.asarray(a,float)); da=(da-da.mean())/da.std(); n=len(da)
    best=None
    for col in range(5):
        db=np.diff(P[:,col]); 
        num=fftconvolve(db, da[::-1], mode='valid')
        c1=np.cumsum(np.r_[0,db]); c2=np.cumsum(np.r_[0,db*db])
        s=c1[n:]-c1[:-n]; ss=c2[n:]-c2[:-n]
        sd=np.sqrt(np.maximum(ss/n-(s/n)**2,1e-30))
        r=num/(n*sd)
        i=int(np.nanargmax(np.abs(r)))
        if best is None or abs(r[i])>abs(best[2]): best=(col,i,r[i])
    out.append((ch,)+best)
    print(f'Fig2A CH{ch}: best F2B column {best[0]} at row {best[1]} (t={best[1]/10/3600:.3f} h if 10 Hz), r(diff)={best[2]:.3f}',flush=True)
