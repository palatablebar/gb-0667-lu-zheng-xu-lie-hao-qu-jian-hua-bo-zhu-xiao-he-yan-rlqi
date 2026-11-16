def normalize(intervals):
    out=[]
    for lo,hi in sorted(intervals):
        if lo>=hi:continue
        if out and lo<=out[-1][1]:out[-1]=(out[-1][0],max(hi,out[-1][1]))
        else:out.append((lo,hi))
    return out

def count(intervals):return sum(b-a for a,b in normalize(intervals))

def covered(intervals,lo,hi):
    return any(a<=lo and b>=hi for a,b in normalize(intervals))

def overlaps(intervals,lo,hi):return any(a<hi and lo<b for a,b in intervals)

def subtract(intervals,lo,hi):
    out=[]
    for a,b in intervals:
        if a<lo:out.append((a,min(b,lo)))
        if b>hi:out.append((max(a,hi),b))
    return normalize(out)
