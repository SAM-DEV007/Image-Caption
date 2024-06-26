# Image-Caption
Generates a caption for the image.

Implementation of the tutorial project provided by [Tensorflow](https://www.tensorflow.org/text/tutorials/image_captioning).

# Requirements
- `pip install -r requirements.txt`.
- Python 3.x or greator. (Python 3.9 used for development here)
- To use the updated model:
    - Download the model from [here](https://drive.google.com/file/d/1cYcKaNmyPMS0Zq-x4ZmVGq6JhIH4fLQe/view?usp=sharing).
    - Copy and extract it to `Model/Model_Data/`, replace the folder if necessary.
    - Make sure the name of the folder is `weights`.

# Model
It uses `Mobile-Net V3 Large` feature extractor to extract the features from the image and Transformer-Decoder to generate the caption.

[Data_Preprocess](Model/Data_Preprocess.ipynb) file contains the code for the preprocessing of the dataset. **(The dataset and its caching space may go over 8GB)**

[Model_Train](Model/Model_Train.ipynb) file contains the code for the training of the model. 

# Working
`caption.py` to initiate and use the model. [Images](Images) folder contains the images to be captioned (sample images are included) and the captioned images are in [Captioned](Images/Captioned) folder generated by the script.
