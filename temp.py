import pydicom

path = r"C:\Users\shoislom.abloberdiev\Desktop\DICOM\DICOM\Abdullayeva D-04122025-113822.DCM"

data = pydicom.dcmread(path)
# print(data.WaveformAnnotationSequence.__dict__)

# print(dir(data))
print(data.WaveformSequence[0])
