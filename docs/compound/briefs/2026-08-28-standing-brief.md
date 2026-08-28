# Standing brief — 2026-08-28

Architecture-expert compound brief (intended for docs/compound/briefs/).
Claims are labeled landed vs provisional. ADRs/policy are not rewritten.

## Seam movement by domain

### architecture
- [landed] **sha:d6bca276e66ef77106d670cdac76cc1ed5c1c26f**: Merge/push to main d6bca276e66ef77106d670cdac76cc1ed5c1c26f
- [provisional] **pr:1742**: (vy)     
- [landed] **sha:755814d7d226808051d16f9d17f80342326e6a2a**: Merge/push to main 755814d7d226808051d16f9d17f80342326e6a2a
- [landed] **pr:1738**:   y    
- [landed] **sha:9cbb4493cc5f1701c6c7789c9cc076fba57d82ca**: Merge/push to main 9cbb4493cc5f1701c6c7789c9cc076fba57d82ca
- [landed] **pr:1673**: (v)       y 
- [landed] **sha:bca812c83bd8def01587dc2c050f8c8bc37ad1fc**: Merge/push to main bca812c83bd8def01587dc2c050f8c8bc37ad1fc
- [landed] **sha:2fb8dcf44bca222df17672867e54b40268e734dc**: Merge/push to main 2fb8dcf44bca222df17672867e54b40268e734dc
- [provisional] **pr:1672**: () x   y
- [landed] **sha:4e13ddde9456f4f7c2363ec5a5a3eac06183a5cc**: Merge/push to main 4e13ddde9456f4f7c2363ec5a5a3eac06183a5cc
- [provisional] **pr:1731**: x(vy)  y  v
- [landed] **sha:3832bdedd6628bb728c1b2b16f368798b035d6c1**: Merge/push to main 3832bdedd6628bb728c1b2b16f368798b035d6c1
- [landed] **sha:1ce277772e59e87da98cff4af3e4d5034d322015**: Merge/push to main 1ce277772e59e87da98cff4af3e4d5034d322015
- [landed] **sha:6e45f58eca27060609aa32b879a4d83830b7623e**: Merge/push to main 6e45f58eca27060609aa32b879a4d83830b7623e
- [landed] **sha:664de3d03873b951d82164b4a46a0655b8faa10b**: Merge/push to main 664de3d03873b951d82164b4a46a0655b8faa10b

### api
- [provisional] **pr:1741**:  y/ .. → .. ()
- [provisional] **pr:1736**: ()   y v
- [provisional] **pr:1733**: () y - v x
- [provisional] **pr:1734**: () y   v x
- [landed] **pr:1732**:  x .. → .. ()
- [provisional] **pr:1731**: x(vy)  y  v
- [landed] **pr:1721**: ()  y-  ..
- [landed] **pr:1709**: ()  -y  ..
- [landed] **pr:1701**: ()  y y  ..
- [landed] **pr:1719**: ()    y  ..
- [provisional] **pr:1722**:  y/ .. → .. ()
- [landed] **pr:1717**: ()  -v  ..
- [landed] **pr:1715**: (vy)  -  y
- [provisional] **pr:1728**: ()   -    y w  
- [landed] **pr:1697**: ()   y  ..

### persistence
- [landed] **pr:1641**: --  -  
- [landed] **pr:1608**: -/-  x     y
- [provisional] **pr:1620**: x   y 
- [provisional] **pr:1619**: x     y 
- [provisional] **pr:1618**: x   y 
- [provisional] **pr:1617**: x   y 
- [provisional] **pr:1616**: x   y 
- [provisional] **pr:1615**: x     y 
- [provisional] **pr:1614**: x   v    y
- [provisional] **pr:1613**: x       
- [provisional] **pr:1612**: x     y 
- [provisional] **pr:1611**: x       
- [provisional] **pr:1610**: x    
- [provisional] **pr:1609**: x      
- [provisional] **pr:1584**: x   x   

### ci-guardrails
- [landed] **pr:1740**: ()     vy
- [landed] **pr:1673**: (v)       y 
- [landed] **pr:1712**: ()     ..
- [landed] **pr:1693**: x()       
- [provisional] **pr:1675**: x()  ww  
- [landed] **pr:1723**: x()  y   y
- [provisional] **pr:1676**: x()  y    v..
- [landed] **pr:1643**: ()  - -w  
- [provisional] **pr:1638**: ()   -    y w  
- [landed] **pr:1641**: --  -  
- [provisional] **pr:1605**: x()      
- [landed] **pr:1625**: x()     v 
- [landed] **pr:1601**: x()  y- ww 
- [landed] **pr:1608**: -/-  x     y
- [provisional] **pr:1620**: x   y 

### rebuild-reconciliation
- [landed] **pr:1455**: x    y 
- [provisional] **pr:1439**: x() v   
- [provisional] **pr:1431**: fix(ci): repair autofix branch gates
- [provisional] **pr:1435**: x()  x  w -
- [provisional] **pr:1427**: x()    
- [provisional] **pr:1424**: fix(ci): clear compound workflow quality gates
- [provisional] **pr:1422**: fix(ci): repair autofix branch failures
- [provisional] **pr:1421**: x()  ww v   
- [provisional] **pr:1414**: x() y    w
- [provisional] **pr:1403**: fix(ci): resolve compound workflow failures

### deployment
- [landed] **pr:1641**: --  -  
- [landed] **pr:1608**: -/-  x     y
- [provisional] **pr:1620**: x   y 
- [provisional] **pr:1619**: x     y 
- [provisional] **pr:1618**: x   y 
- [provisional] **pr:1617**: x   y 
- [provisional] **pr:1616**: x   y 
- [provisional] **pr:1615**: x     y 
- [provisional] **pr:1614**: x   v    y
- [provisional] **pr:1613**: x       
- [provisional] **pr:1612**: x     y 
- [provisional] **pr:1611**: x       
- [provisional] **pr:1610**: x    
- [provisional] **pr:1609**: x      
- [landed] **pr:1529**: (--)   z   w  -
