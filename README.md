# BMDS2133 Image Processing Assignment
## FaceCert - Intelligent Face Recognition and Barcode Detection for Graduation Ceremony

### Models / Algorithms used:
- Insight Face
    * Face Recognition
- MTCNN with FaceNet
    * Face Recognition
- Pyzbar
    * Generate Barcode 
- Zxingcpp
    * Generate QR code
- DeepSort
    * Human Tracking
- YOLOv8
    * Human Tracking

### Flow
1. A barcode will be generated first and sent to graduates before the graduation ceremony.
2. The graduates should scan their face and the barcode at Counter A to confirm the attendance. A qr code (token) will be generated and sent to the student email.
3. During queueing up at the stairs, graduates should use scan the qr code to confirm their name and cerfication.
4. There will be a camera at the center of the hall. It will capture the whole stage. If the graduate is walking from one side to another side of the stage, it will automatically announce the next graduate with the picture on the screen.