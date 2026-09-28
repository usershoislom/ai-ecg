import wfdb

pathes = [r"C:\\Users\\shoislom.abloberdiev\\Desktop\\ecg_datasets_hypertrophy\\ecg_datasets_hypertrophy\\LUDB\\LAE\\2",
    r"C:\\Users\\shoislom.abloberdiev\\Desktop\\ecg_datasets_hypertrophy\\ecg_datasets_hypertrophy\\Pediatric_ECG_Hypertrophy\\LAE\\P00816_E01",
    r"C:\\Users\\shoislom.abloberdiev\\Desktop\\ecg_datasets_hypertrophy\\ecg_datasets_hypertrophy\\PhysioNet Challenge 2021\\LAE\\E00030"
    ]
for p in pathes:
    r = wfdb.rdrecord(p)
    print(p, '| fs:', r.fs, '| leads:', r.n_sig, '| len:', r.sig_len,
          '| names:', r.sig_name, '| units:', r.units)