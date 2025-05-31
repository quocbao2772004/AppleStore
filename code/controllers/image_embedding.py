import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
# import onnxruntime as ort

import numpy as np
from PIL import Image
from torchvision import transforms
import faiss

import torch
import torch.nn.functional as F
from transformers import AutoImageProcessor, AutoModel
from PIL import Image
# --- CONFIG ---
MODEL_PATH = "/home/anonymous/code/web/v0/controllers/data/model.onnx"
IMAGE_FOLDER = "/home/anonymous/code/web/v0/uploads/assets/images"
QUERY_IMAGE = "/home/anonymous/code/web/v0/uploads/assets/images/airpod/0000211_airpods-pro-2_240.png"
INDEX_PATH = "/home/anonymous/code/web/v0/controllers/data/faiss.index"
FILENAMES_PATH = "/home/anonymous/code/web/v0/controllers/data/filenames.npy"

# --- ONNX session ---
# session = ort.InferenceSession(MODEL_PATH, providers=["CUDAExecutionProvider"])

# --- Tiền xử lý ảnh ---
transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.5]*3, std=[0.5]*3)
])

def l2_normalize(x):
    return x / np.linalg.norm(x)
processor = AutoImageProcessor.from_pretrained("nomic-ai/nomic-embed-vision-v1.5", use_fast=True)
vision_model = AutoModel.from_pretrained("nomic-ai/nomic-embed-vision-v1.5", trust_remote_code=True).to("cuda")
vision_model.eval()

# Hàm tạo embedding từ ảnh
def embeddingImage(path):
    image = Image.open(path).convert("RGB")
    inputs = processor(images=image, return_tensors="pt")
    inputs = {k: v.to("cuda") for k, v in inputs.items()}

    with torch.no_grad():
        outputs = vision_model(**inputs).last_hidden_state  # shape (1, 197, 768)
        embeddings = F.normalize(outputs[:, 0], p=2, dim=1)  # lấy CLS token, chuẩn hóa
        vector = embeddings.squeeze(0).cpu().numpy()  # shape (768,)

    return vector
# --- Tạo embedding từ ảnh ---
# def embeddingImage(path):
#     img = Image.open(path).convert("RGB")
#     img_tensor = transform(img).unsqueeze(0).numpy()
#     inputs = {session.get_inputs()[0].name: img_tensor}
#     outputs = session.run(None, inputs)
#     embedding = outputs[0][0][0]  # Lấy CLS token: shape (768,)
#     return embedding

# --- PHẦN 1: TẠO FAISS INDEX 
def create_faiss_index():
    if not os.path.exists(INDEX_PATH):
        embeddings = []
        file_names = []

        for folder_name in os.listdir(IMAGE_FOLDER):
            if folder_name.endswith(".png"):
                continue  
            path = os.path.join(IMAGE_FOLDER, folder_name)
            for file_name in os.listdir(path):
                image_path = os.path.join(path, file_name)
                if os.path.isfile(image_path):
                    emb = embeddingImage(image_path)
                    norm_emb = l2_normalize(emb)
                    embeddings.append(norm_emb)
                    file_names.append(file_name)

        embeddings_np = np.vstack(embeddings).astype(np.float32)
        index = faiss.IndexFlatL2(768)
        index.add(embeddings_np)

        faiss.write_index(index, INDEX_PATH)
        np.save(FILENAMES_PATH, np.array(file_names))
        print("✅ Đã lưu FAISS index và tên file.")

# --- PHẦN 2: TÌM ẢNH TƯƠNG TỰ ---
def find_similar_images(query_image, top_k = 1):
    index = faiss.read_index(INDEX_PATH)
    file_names = np.load(FILENAMES_PATH)

    query_emb = embeddingImage(query_image)
    query_emb = l2_normalize(query_emb).astype(np.float32).reshape(1, -1)

    distances, indices = index.search(query_emb, top_k)

    results = []
    for dist, idx in zip(distances[0], indices[0]):
        results.append({
            "filename": file_names[idx],
            "distance": round(float(dist), 4)
        })
    return results