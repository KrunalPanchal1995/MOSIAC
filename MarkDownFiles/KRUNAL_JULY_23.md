<!--
Relocated 2026-08-04 from the repo root to MarkDownFiles/ (hygiene pass, see
bug.md). ~70 source files across the repo cite this file by name only (e.g.
"KRUNAL_JULY_23.md point 4") as a stable label for one of the 8 points below --
none of them open it by path, so the move doesn't break anything; citations
were deliberately not bulk-edited across all 70 files for a purely cosmetic
path-prefix change. If you're looking for one of those citations, this is the
file.
-->

Add option of exporting the status of the run from any GUI into a txt file (for eg: which file locations were used, what was the output location, then options selected and error or output printed)
I tried generating the CHEMKIN convertor, for KONNOV_2019 mechanism, it failed because of this error
=== CHEMKIN preflight: 6 error(s), 277 warning(s), 1 info ===
  ✗ [error] line 70: Fortran-style exponent '-2' missing the 'E' (e.g. 1.7-13 → 1.7E-13) — a top cause of ck2yaml parse failures.
  ✗ [error] line 71: Fortran-style exponent '-2' missing the 'E' (e.g. 1.7-13 → 1.7E-13) — a top cause of ck2yaml parse failures.
  ✗ [error] line 526: Fortran-style exponent '-2' missing the 'E' (e.g. 1.7-13 → 1.7E-13) — a top cause of ck2yaml parse failures.
  ✗ [error] line 527: Fortran-style exponent '-2' missing the 'E' (e.g. 1.7-13 → 1.7E-13) — a top cause of ck2yaml parse failures.
  ✗ [error] line 535: Fortran-style exponent '-2' missing the 'E' (e.g. 1.7-13 → 1.7E-13) — a top cause of ck2yaml parse failures.
  ✗ [error] line 536: Fortran-style exponent '-2' missing the 'E' (e.g. 1.7-13 → 1.7E-13) — a top cause of ck2yaml parse failures.
  ▲ [warning] line 98: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 99: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 100: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 101: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 102: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 103: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 104: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 105: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 106: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 107: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 108: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 109: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 110: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 111: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 112: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 113: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 114: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 115: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 116: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 117: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 118: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 121: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 122: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 123: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 124: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 125: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 126: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 127: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 128: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 129: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 130: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 131: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 132: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 133: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 134: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 135: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 136: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 137: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1723: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1725: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1726: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1728: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1729: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1730: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1731: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1732: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1733: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1734: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1735: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1736: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1737: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1738: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1739: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1740: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1741: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1742: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1743: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1744: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1746: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1748: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1749: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1750: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1751: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1752: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1753: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1754: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1755: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1756: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1757: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1758: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1760: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1761: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1762: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1763: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1764: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1765: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1766: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1767: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1768: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1769: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1770: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1771: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1772: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1773: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1774: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1775: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1776: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1777: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1778: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1779: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1780: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1781: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1782: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1783: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1784: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1785: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1787: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1788: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1789: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1790: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1791: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1792: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1793: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1794: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1795: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1796: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1797: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1798: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1799: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1800: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1801: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1802: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1803: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1804: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1805: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1806: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1807: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1808: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1809: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1810: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1811: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1812: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1813: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1814: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1817: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1818: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1819: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1820: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1821: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1823: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1825: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1826: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1827: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1828: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1829: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1830: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1831: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1832: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1833: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1834: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1835: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1836: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1837: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1838: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1839: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1840: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1841: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1842: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1843: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1844: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1845: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1846: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1847: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1848: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1849: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1850: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1851: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1852: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1853: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1854: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1855: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1856: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1857: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1858: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1859: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1860: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1861: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1862: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1863: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1864: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1865: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1866: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1867: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1868: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1869: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1870: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1871: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1872: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1873: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1874: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1875: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1876: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1877: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1878: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1879: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1880: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1881: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1882: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1883: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1884: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1885: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1886: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1887: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1888: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1889: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1890: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1891: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1892: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1893: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1894: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1895: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1896: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1897: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1898: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1899: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1900: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1901: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1902: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1903: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1904: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1905: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1906: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1907: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1908: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1909: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1910: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1911: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1912: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1913: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1914: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1915: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1916: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1917: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1918: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1919: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1920: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1921: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1922: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1923: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1924: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1925: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1926: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1927: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1928: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1929: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1930: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1931: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1932: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1933: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1934: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1935: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1936: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1937: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1938: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1939: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1940: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1941: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1942: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1943: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1944: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1945: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1946: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1947: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1948: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1949: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1950: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1951: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1952: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1953: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1955: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1957: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1958: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1959: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1960: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1961: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1962: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1963: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1964: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1965: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1966: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1967: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1968: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1969: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1970: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1971: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1972: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  ▲ [warning] line 1973: Tab character in a data line — CHEMKIN is column/whitespace sensitive; replace tabs with spaces.
  • [info] line 139: REACTIONS header declares no units — CHEMKIN defaults to cal/mole & moles; confirm that matches the rate data (the J/kmol vs cal/mol trap).
Preprocessing input files…
  [fix] 2 Fortran exponent(s) repaired in 128-957.inp
  [fix] CRLF -> LF: 128-957.dat
  [fix] 50 Fortran exponent(s) repaired in 128-957.dat

=== ck2yaml -> Cantera YAML ===
$ /home/krithika/anaconda3/bin/ck2yaml --input=/data/MECHANISM_OPTIMIZATION_SUITE/MECHANISM/KONNOV_2019_AMMONIA_HYDROGEN/fixed_128-957.inp --thermo=/data/MECHANISM_OPTIMIZATION_SUITE/MECHANISM/KONNOV_2019_AMMONIA_HYDROGEN/fixed_128-957.dat --transport=/data/MECHANISM_OPTIMIZATION_SUITE/MECHANISM/KONNOV_2019_AMMONIA_HYDROGEN/128-957.tran --output=/data/MECHANISM_OPTIMIZATION_SUITE/MECHANISM/KONNOV_2019_AMMONIA_HYDROGEN/128-957.yaml --permissive --no-validate
  Error reading reaction starting on line 484:
  """
  C2H5+O2<=>C2H4O1-2+OH                                        +1.3030000E+003 +1.9300000E+000 -5.0270000E+002
  PLOG /     +4.0000000E-002 +1.3030000E+003 +1.9300000E+000 -5.0270000E+002 /
  PLOG /     +1.0000000E+000 +2.4380000E+002 +2.1800000E+000 -6.2500000E+001 /
  PLOG /     +1.0000000E+001 +4.6210000E+009 +1.5000000E-001 +5.4090000E+003 /
  """
  
  ERROR: Unable to parse '/data/MECHANISM_OPTIMIZATION_SUITE/MECHANISM/KONNOV_2019_AMMONIA_HYDROGEN/fixed_128-957.inp' near line 484:
  Unexpected token "C2H4O1-2+" in reaction expression "C2H5+O2<=>C2H4O1-2+OH
  ".
  Please check https://cantera.org/tutorials/ck2yaml-tutorial.html#debugging-common-errors-in-ck-files
  for the correct Chemkin syntax.
  
  Traceback (most recent call last):
    File "/home/krithika/anaconda3/lib/python3.9/site-packages/cantera/ck2yaml.py", line 1107, in read_kinetics_entry
      locs[j] = int(token), 'coeff'
  ValueError: invalid literal for int() with base 10: 'C2H4O1-2+'
  
  During handling of the above exception, another exception occurred:
  
  Traceback (most recent call last):
    File "/home/krithika/anaconda3/lib/python3.9/site-packages/cantera/ck2yaml.py", line 1110, in read_kinetics_entry
      locs[j] = float(token), 'coeff'
  ValueError: could not convert string to float: 'C2H4O1-2+'
  
  During handling of the above exception, another exception occurred:
  
  Traceback (most recent call last):
    File "/home/krithika/anaconda3/bin/ck2yaml", line 8, in <module>
      sys.exit(script_entry_point())
    File "/home/krithika/anaconda3/lib/python3.9/site-packages/cantera/ck2yaml.py", line 2294, in script_entry_point
      main(sys.argv[1:])
    File "/home/krithika/anaconda3/lib/python3.9/site-packages/cantera/ck2yaml.py", line 2258, in main
      parser, surfaces = Parser.convert_mech(input_file, thermo_file,
    File "/home/krithika/anaconda3/lib/python3.9/site-packages/cantera/ck2yaml.py", line 2091, in convert_mech
      parser.load_chemkin_file(input_file)
    File "/home/krithika/anaconda3/lib/python3.9/site-packages/cantera/ck2yaml.py", line 1841, in load_chemkin_file
      reaction, revReaction = self.read_kinetics_entry(kinetics, surface)
    File "/home/krithika/anaconda3/lib/python3.9/site-packages/cantera/ck2yaml.py", line 1112, in read_kinetics_entry
      raise InputError('Unexpected token "{}" in reaction expression "{}".',
  cantera.ck2yaml.InputError: Unexpected token "C2H4O1-2+" in reaction expression "C2H5+O2<=>C2H4O1-2+OH
  ".
  Please check https://cantera.org/tutorials/ck2yaml-tutorial.html#debugging-common-errors-in-ck-files
  for the correct Chemkin syntax.

=== ScanMan -> FlameMaster .pre ===
$ /home/krithika/FlameMaster/Bin/bin/ScanMan -i /data/MECHANISM_OPTIMIZATION_SUITE/MECHANISM/KONNOV_2019_AMMONIA_HYDROGEN/fixed_128-957.inp -t /data/MECHANISM_OPTIMIZATION_SUITE/MECHANISM/KONNOV_2019_AMMONIA_HYDROGEN/fixed_128-957.dat -m /data/MECHANISM_OPTIMIZATION_SUITE/MECHANISM/KONNOV_2019_AMMONIA_HYDROGEN/128-957.tran -f chemkin -E -c -N 0.05 -o /data/MECHANISM_OPTIMIZATION_SUITE/MECHANISM/KONNOV_2019_AMMONIA_HYDROGEN/128-957.pre
  ScanMan preprocessor program
  
  Cannot find species 'C2H4O1-2' in species list!
  version                  4.2.1
  executed command         '/home/krithika/FlameMaster/Bin/bin/ScanMan -i /data/MECHANISM_OPTIMIZATION_SUITE/MECHANISM/KONNOV_2019_AMMONIA_HYDROGEN/fixed_128-957.inp -t /data/MECHANISM_OPTIMIZATION_SUITE/MECHANISM/KONNOV_2019_AMMONIA_HYDROGEN/fixed_128-957.dat -m /data/MECHANISM_OPTIMIZATION_SUITE/MECHANISM/KONNOV_2019_AMMONIA_HYDROGEN/128-957.tran -f chemkin -E -c -N 0.05 -o /data/MECHANISM_OPTIMIZATION_SUITE/MECHANISM/KONNOV_2019_AMMONIA_HYDROGEN/128-957.pre'
  operating system         Linux, version 5.11.0-43-generic
  target architechture     x86_64
  c++ compiler             GNU, version 9.3.0
  c   compiler             GNU, version 9.3.0

=== rmip parse -> database ===
$ /home/krithika/anaconda3/bin/python3.9 /data/MECHANISM_OPTIMIZATION_SUITE/rmip_cli.py parse /data/MECHANISM_OPTIMIZATION_SUITE/MECHANISM/KONNOV_2019_AMMONIA_HYDROGEN/fixed_128-957.inp --db /data/MECHANISM_OPTIMIZATION_SUITE/outputs/project.db --name 128-957 --thermo /data/MECHANISM_OPTIMIZATION_SUITE/MECHANISM/KONNOV_2019_AMMONIA_HYDROGEN/fixed_128-957.dat --glossary /data/MECHANISM_OPTIMIZATION_SUITE/species_smiles.csv
  12:09:15 [INFO] rmip.core.parser: Parsing mechanism: /data/MECHANISM_OPTIMIZATION_SUITE/MECHANISM/KONNOV_2019_AMMONIA_HYDROGEN/fixed_128-957.inp (format=chemkin)
  12:09:15 [INFO] rmip.io.glossary: Loaded glossary: 35 entries from '/data/MECHANISM_OPTIMIZATION_SUITE/species_smiles.csv'
  12:09:15 [INFO] rmip.io.chemkin: Loading CHEMKIN file: /data/MECHANISM_OPTIMIZATION_SUITE/MECHANISM/KONNOV_2019_AMMONIA_HYDROGEN/fixed_128-957.inp
  12:09:15 [WARNING] rmip.io.chemkin: RMG-Py not available; using built-in CHEMKIN parser. For full resonance structure support, install RMG-Py.
  12:09:16 [ERROR] rmip.io.chemkin_parser: Reaction 'C2H5 + O2 <=> C2H4O1-2 + OH': undeclared participant(s) ['C2H4O1-2'] -- not present in the SPECIES block. Pass allow_pseudo_species=True to ChemkinParser() to drop such tokens (e.g. chemiluminescence bookkeeping species like HV) instead of keeping them.
  12:09:16 [ERROR] rmip.io.chemkin_parser: Reaction 'C2H5O2 <=> C2H4O1-2 + OH': undeclared participant(s) ['C2H4O1-2'] -- not present in the SPECIES block. Pass allow_pseudo_species=True to ChemkinParser() to drop such tokens (e.g. chemiluminescence bookkeeping species like HV) instead of keeping them.
  12:09:16 [ERROR] rmip.io.chemkin_parser: Reaction 'C2H4O2H <=> C2H4O1-2 + OH': undeclared participant(s) ['C2H4O1-2'] -- not present in the SPECIES block. Pass allow_pseudo_species=True to ChemkinParser() to drop such tokens (e.g. chemiluminescence bookkeeping species like HV) instead of keeping them.
  12:09:16 [ERROR] rmip.io.chemkin_parser: Reaction 'C2H4O1-2 <=> CH3 + HCO': undeclared participant(s) ['C2H4O1-2'] -- not present in the SPECIES block. Pass allow_pseudo_species=True to ChemkinParser() to drop such tokens (e.g. chemiluminescence bookkeeping species like HV) instead of keeping them.
  12:09:16 [ERROR] rmip.io.chemkin_parser: Reaction 'C2H4O1-2 <=> CH3CHO': undeclared participant(s) ['C2H4O1-2'] -- not present in the SPECIES block. Pass allow_pseudo_species=True to ChemkinParser() to drop such tokens (e.g. chemiluminescence bookkeeping species like HV) instead of keeping them.
  12:09:16 [ERROR] rmip.io.chemkin_parser: Reaction 'C2H4O1-2 + H <=> C2H3O1-2 + H2': undeclared participant(s) ['C2H4O1-2', 'C2H3O1-2'] -- not present in the SPECIES block. Pass allow_pseudo_species=True to ChemkinParser() to drop such tokens (e.g. chemiluminescence bookkeeping species like HV) instead of keeping them.
  12:09:16 [ERROR] rmip.io.chemkin_parser: Reaction 'C2H4O1-2 + OH <=> C2H3O1-2 + H2O': undeclared participant(s) ['C2H4O1-2', 'C2H3O1-2'] -- not present in the SPECIES block. Pass allow_pseudo_species=True to ChemkinParser() to drop such tokens (e.g. chemiluminescence bookkeeping species like HV) instead of keeping them.
  12:09:16 [ERROR] rmip.io.chemkin_parser: Reaction 'C2H4O1-2 + HO2 <=> C2H3O1-2 + H2O2': undeclared participant(s) ['C2H4O1-2', 'C2H3O1-2'] -- not present in the SPECIES block. Pass allow_pseudo_species=True to ChemkinParser() to drop such tokens (e.g. chemiluminescence bookkeeping species like HV) instead of keeping them.
  12:09:16 [ERROR] rmip.io.chemkin_parser: Reaction 'C2H4O1-2 + CH3 <=> C2H3O1-2 + CH4': undeclared participant(s) ['C2H4O1-2', 'C2H3O1-2'] -- not present in the SPECIES block. Pass allow_pseudo_species=True to ChemkinParser() to drop such tokens (e.g. chemiluminescence bookkeeping species like HV) instead of keeping them.
  12:09:16 [ERROR] rmip.io.chemkin_parser: Reaction 'C2H4O1-2 + CH3O <=> C2H3O1-2 + CH3OH': undeclared participant(s) ['C2H4O1-2', 'C2H3O1-2'] -- not present in the SPECIES block. Pass allow_pseudo_species=True to ChemkinParser() to drop such tokens (e.g. chemiluminescence bookkeeping species like HV) instead of keeping them.
  12:09:16 [ERROR] rmip.io.chemkin_parser: Reaction 'C2H4O1-2 + CH3O2 <=> C2H3O1-2 + CH3O2H': undeclared participant(s) ['C2H4O1-2', 'C2H3O1-2'] -- not present in the SPECIES block. Pass allow_pseudo_species=True to ChemkinParser() to drop such tokens (e.g. chemiluminescence bookkeeping species like HV) instead of keeping them.
  12:09:16 [ERROR] rmip.io.chemkin_parser: Reaction 'C2H4O1-2 + C2H5O2 <=> C2H3O1-2 + C2H5O2H': undeclared participant(s) ['C2H4O1-2', 'C2H3O1-2'] -- not present in the SPECIES block. Pass allow_pseudo_species=True to ChemkinParser() to drop such tokens (e.g. chemiluminescence bookkeeping species like HV) instead of keeping them.
  12:09:16 [ERROR] rmip.io.chemkin_parser: Reaction 'C2H3O1-2 <=> CH3CO': undeclared participant(s) ['C2H3O1-2'] -- not present in the SPECIES block. Pass allow_pseudo_species=True to ChemkinParser() to drop such tokens (e.g. chemiluminescence bookkeeping species like HV) instead of keeping them.
  12:09:16 [ERROR] rmip.io.chemkin_parser: Reaction 'C2H3O1-2 <=> CH2CHO': undeclared participant(s) ['C2H3O1-2'] -- not present in the SPECIES block. Pass allow_pseudo_species=True to ChemkinParser() to drop such tokens (e.g. chemiluminescence bookkeeping species like HV) instead of keeping them.
  12:09:16 [ERROR] rmip.io.chemkin_parser: Reaction 'C2H4 + HO2 <=> C2H4O1-2 + OH': undeclared participant(s) ['C2H4O1-2'] -- not present in the SPECIES block. Pass allow_pseudo_species=True to ChemkinParser() to drop such tokens (e.g. chemiluminescence bookkeeping species like HV) instead of keeping them.
  12:09:16 [ERROR] rmip.io.chemkin_parser: Reaction 'C2H4 + CH3O2 <=> C2H4O1-2 + CH3O': undeclared participant(s) ['C2H4O1-2'] -- not present in the SPECIES block. Pass allow_pseudo_species=True to ChemkinParser() to drop such tokens (e.g. chemiluminescence bookkeeping species like HV) instead of keeping them.
  12:09:16 [ERROR] rmip.io.chemkin_parser: Reaction 'C2H4 + C2H5O2 <=> C2H4O1-2 + C2H5O': undeclared participant(s) ['C2H4O1-2'] -- not present in the SPECIES block. Pass allow_pseudo_species=True to ChemkinParser() to drop such tokens (e.g. chemiluminescence bookkeeping species like HV) instead of keeping them.
  12:09:16 [INFO] rmip.io.chemkin_parser: ChemkinParser: 644 species, 957 reactions parsed from /data/MECHANISM_OPTIMIZATION_SUITE/MECHANISM/KONNOV_2019_AMMONIA_HYDROGEN/fixed_128-957.inp
  12:09:16 [INFO] rmip.io.chemkin:   Raw: 644 species, 957 reactions
  12:09:16 [INFO] rmip.core.parser: Stored mechanism id=14: 644 species, 957 reactions
  
  ✓ Mechanism stored as id=14
    Name:         128-957
    Species:      644
    Reactions:    957
    Glossary hit: 5.4%
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: Accepted unusual valence(s): O(1)
  
  [12:09:16] WARNING: Accepted unusual valence(s): O(1)
  
  [12:09:16] WARNING: Accepted unusual valence(s): O(1)
  
  [12:09:16] WARNING: Accepted unusual valence(s): C(3)
  
  [12:09:16] WARNING: Accepted unusual valence(s): N(2)
  
  [12:09:16] WARNING: Accepted unusual valence(s): O(1)
  
  [12:09:16] WARNING: Charges were rearranged; Accepted unusual valence(s): O(1)
  
  [12:09:16] WARNING: Charges were rearranged
  
  [12:09:16] WARNING: Accepted unusual valence(s): N(1)
  
  [12:09:16] WARNING: Accepted unusual valence(s): O(1)
  
  [12:09:16] WARNING: Accepted unusual valence(s): N(2)
  
  [12:09:16] WARNING: Charges were rearranged
  
  [12:09:16] WARNING: Accepted unusual valence(s): N(2)
  
  [12:09:16] WARNING: Accepted unusual valence(s): N(1)
  
  [12:09:16] WARNING: Accepted unusual valence(s): N(2)
  
  [12:09:16] WARNING: Omitted undefined stereo
  
  [12:09:16] WARNING: Accepted unusual valence(s): N(1)
  
  [12:09:16] WARNING: Accepted unusual valence(s): N(2)
  
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
  [12:09:16] WARNING: not removing hydrogen atom without neighbors
✓ mechanism ingested into /data/MECHANISM_OPTIMIZATION_SUITE/outputs/project.db

ERROR: ck2yaml failed (exit 1) — full output above. Common causes: Fortran exponents without E (enable the auto-fix), undeclared species used in reactions (vendor lumping comments), miswritten thermo columns, non-standard REACTIONS-line tokens, undeclared DUPLICATE reactions.
ERROR: ScanMan failed (exit 2) — full output above.

Fix this, and deploy a code that does fix this automatically without user inputs. And you can also allow the user to open the file here in GUI itself (gedit it self should be embedded here) Then alloow the user to make appropriate changes and then re-run the task (DO THIS IN EVERY GUI)
--------------------------------------------------------------------------------------------------
I tried Mechanism helth check
I used the same KONNOV mechanism. I found that you cannot even copy the error msg. it says LOAD failes. It seems that you only allow YAML mech. Then state it somewhere or do not show any other foamte files when I load the files. But it seems to work. Make the errors thrown more descriptive. ALso give examples on how they can fix the issue raised.
I feel that you have not made the GUI in PySide6, but in Tkinker. ALL GUI must be in pyside6, justify your stance
--------------------------------------------------------------------------------------------------
THere is a need for complete overhaul of Ignition-delay sensitivity GUI. First of all using Brute force method, you can do sensitivity analysis of any targets. Go read the src/MUQ-SAC/make_input_file.py and implemt the options given there: for eg: SOlver, Ignition delay def, all the add files options, etc) You must replicat that here in GUI so user can give the options here, there must be an default options loaded already so user can know what to select. Same for nominal simulations. THey can either provide list of targets and add file for options or they can do this manually also. Take care of the request I am giving you here. All multi-processes case must run as I have coded in my src folder
The output looks good, but you must allow the user to make many changes in plots like export version, color scheme, font size, text, annotation, etc every option that matplot lib provides must be availabel in this GUI
--------------------------------------------------------------------------------------------------
You miss understood about the Uncertainty Generator, first of all change the name to say Uncertinity Quantification and file generator etc some thing that exactly matches the case we are running. Then when I generate xml files, I use SA data and csv files as inputs. I never give reaction mannually. You must allow the user to do the same. Go understand how "/data/MECHANISM_OPTIMIZATION_SUITE/src/ActiveParameterScreen.py" this code works and here is an example you can run to test the above code "/home/krithika/mechanism-optimization-suite/DATASET/METHYL_BUTANOATE_2026/ACTIVE_PARAMETER_SELECTION/clt" this file has commanda you can run in terminal. Literally all the options must be here in this GUI. The SA must give the output files like how I am giving in my case. THAT output can be used here as input and generate all sorts of things as given in the code

_---------------------------------------------------------------------------------------------
I do not know how you passed the GUI mech fusion, I tried to run fusion on : GRI-3.0 (chemkin, 15 sp / 48 rxn)
2: Davis-2005 (chemkin, 14 sp / 38 rxn)
3: Keromenes-2013 (chemkin, 17 sp / 49 rxn)
4: Li-2015 (chemkin, 14 sp / 37 rxn)
5: FFCM1 (cantera_yaml, 38 sp / 291 rxn)
6: MB-MB2D (base) (cantera_yaml, 608 sp / 3984 rxn)
7: MB-MB2D Lalit-2024 (cantera_yaml, 623 sp / 4050 rxn)
8: GRI-3.0 (chemkin, 15 sp / 48 rxn)
9: Davis-2005 (chemkin, 14 sp / 38 rxn)
10: Keromenes-2013 (chemkin, 17 sp / 49 rxn)
11: Li-2015 (chemkin, 14 sp / 37 rxn)
12: Fused_Mech (fused, 0 sp / 0 rxn)
13: Fused_Mech (fused, 0 sp / 0 rxn)
14: 128-957 (chemkin, 644 sp / 957 rxn)
2,3,4, but it did not generated the fused mechanism. DO RUN THE GUI again and do fuse these three mechsnism. See what errors are generated, fix the bugs till it gives fused mechsnims. It must also generate the uncertainty data for all the reactions. You must provide an output file so It can be used as input to uncertainty file generator. The format must match what the updated Uncertainty Generator requires
----------------------------------------------------------------------------------------------------
RMIP gave this as output:
Graph comparison: mechs [2, 3, 4]                                                                        
  Species   — universal: 0, partial: 0, unique: 45                                                       
  Reactions — identical: 0, divergent: 0, unique: 124                                                    
✓ Classification → outputs/graph_cmp/graph_classification.json                                           
12:40:07 [INFO] rmip.analysis.graph_comparator: UnionGraphSpec built: 45 species | 124 verbatim + 0 copy 
+ 0 fuse reactions                                                                                       
✓ Union graph spec → outputs/graph_cmp/union_graph_spec.json                                             
  Verbatim reactions (unique):    124                                                                    
  Copy reactions (identical):     0                                                                      
  Fuse reactions (divergent→MSO): 0                                                                      
                                                                                                         
  → Hand union_graph_spec.json to M7 FusionEngine (Phase 4)                                              
  → Hand fuse_params in that file to M9 DoEFramework (Phase 4)                                           
                                                                                                         

[process exited]

But it did not gave link to local server host where I can see the graph. Do that. AND each and every option of the python code and options must also be here in this GUI
---------------------------------------------------------------------------------------------------
WHere are the GUIs to create target.opt, *.target files and *.add files, also where is the .so file generators? I do not see those in the list. ADD those also, what about the PySR, LATEX, pLOT DIGITIZERS AND jUPYTER NOTEBOOKS OR AI integration like google notebook etc? ADD THOSE ALSO

