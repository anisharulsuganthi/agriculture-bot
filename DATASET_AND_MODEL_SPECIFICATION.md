# Plant Disease Detection: Dataset and Model Technical Specification

---

## 1. Executive Summary

This project implements an end-to-end Computer Vision system for diagnosing agricultural crop health and identifying plant diseases from leaf imagery. The system is designed to classify leaf photographs into **332 distinct disease, pest, nutrient deficiency, and healthy states** across **42 agricultural crops and horticultural plants**. 

The underlying model is built on **MobileNetV2**, optimized with transfer learning, partial layer fine-tuning, dynamic data augmentation, and stratified sampling to provide rapid inference suitable for edge and production deployments.

---

## 2. Dataset Technical Profile

### 2.1 Overview & Scale
* **Total Image Count:** 66,953 labeled RGB leaf images
* **Total Unique Classes:** 332 classification targets
* **Crop Varieties Covered:** 42 unique botanical species
* **Master Manifest:** `dataset 1/metadata/metadata/dataset_manifest.csv`
* **Deduplication Manifest:** `dataset 1/metadata/metadata/dedup_manifest.csv`
* **Image Repository:** `dataset 1/master_images/master_images/images/`

### 2.2 Data Sources & Aggregation
The dataset is a multi-source master compilation harmonizing prominent international plant pathology benchmarks into a unified schema:
1. **PlantVillage Dataset:** Comprehensive benchmark covering solanaceous, cucurbit, and rosaceous crops.
2. **BPLD (Blackgram Plant Leaf Disease Dataset):** Field and laboratory imagery for legume pathology.
3. **Sugarcane Leaf Disease Dataset:** Specific fungal and viral markers (Red Rot, Yellow Leaf, Rust).
4. **Rice/Paddy Disease Datasets:** Blast, Hispa, Tungro, and stem borer manifestations.
5. **Specialized Field Surveys:** Additional citrus, banana, coffee, and groundnut surveys.

### 2.3 Covered Plant Species (42 Species)

| Category | Plant Species |
| :--- | :--- |
| **Cereals & Staples** | Rice (Paddy), Wheat, Corn (Maize), Potato, Sugarcane |
| **Legumes & Pulses** | Groundnut (Peanut), Soybean, Blackgram, Bean |
| **Solanaceous Vegetables** | Tomato, Bell Pepper, Chilli, Eggplant (Brinjal) |
| **Cruciferous & Root Crops** | Cabbage, Cauliflower, Broccoli, Carrot, Radish |
| **Cucurbits & Greens** | Cucumber, Zucchini, Squash, Celery, Lettuce |
| **Fruits & Berries** | Banana, Apple, Grape, Strawberry, Cherry, Blueberry, Raspberry, Peach, Plum, Citrus |
| **Plantation & Commercial** | Coffee, Tobacco, Basil, Garlic, Ginger, Maple |

### 2.4 Disease Taxonomy & Pathology Classes
The 332 classes capture a broad spectrum of plant pathology:
* **Fungal Pathogens:** Early Blight (*Alternaria*), Late Blight (*Phytophthora*), Powdery Mildew, Rusts (*Puccinia*), Anthracnose, Leaf Spots (*Cercospora*, *Septoria*, *Isariopsis*).
* **Bacterial Infections:** Bacterial Spot (*Xanthomonas*), Bacterial Wilt, Black Rot.
* **Viral Pathogens:** Yellow Leaf Curl Virus (TYLCV), Mosaic Viruses (Sugarcane Mosaic, Yellow Mosaic), Tungro Virus.
* **Pest & Arthropod Damage:** Two-Spotted Spider Mites, Hispa beetles, Stem Borer (Dead Heart).
* **Nutritional & Abiotic Stress:** Nitrogen, phosphorus, and potassium deficiencies; physiological chlorosis.
* **Healthy Baselines:** Asymptomatic leaf controls for every crop variety.

### 2.5 Data Preprocessing & Augmentation Pipeline
To mitigate overfitting across the 332 classes and simulate varying natural field conditions:

```
Raw Image (Variable Dimensions)
   │
   ▼
Resize & Bilinear Interpolation (224 × 224 pixels)
   │
   ▼
Random Horizontal Flip (p = 0.5)
   │
   ▼
Random Affine Rotation (-15° to +15°)
   │
   ▼
Color Jitter (Brightness ±10%, Contrast ±10%, Saturation ±10%)
   │
   ▼
Tensor Conversion & Channel Normalization:
   Mean: [0.485, 0.456, 0.406]
   Std:  [0.229, 0.224, 0.225]
```

### 2.6 Partitioning & Stratification Strategy
* **Split Ratio:** 80% Training (53,563 images) / 20% Validation (13,390 images).
* **Stratification Handling:** Standard Stratified $k$-fold requires $\ge 2$ samples per class. For rare singleton categories (e.g., classes with only 1 representative sample), samples are deterministically retained in the training set, while remaining classes are stratified evenly to maintain identical class probability distributions in both partitions.

---

## 3. Machine Learning Model Architecture

### 3.1 Base Architecture: MobileNetV2
* **Architectural Family:** Deep Inverted Residual Convolutional Neural Network
* **Developers:** Google Research (Sandler et al., 2018)
* **Pretrained Weights:** ImageNet-1K (`MobileNet_V2_Weights.DEFAULT`)
* **Input Tensor Shape:** `[Batch_Size, 3, 224, 224]`

### 3.2 Model Parameters & Footprint
* **Total Parameters:** **2,649,164** (~2.65 Million)
* **Pretrained Base Parameters:** 3,504,872 (originally for 1,000 ImageNet classes)
* **Classifier Adaptation:**
  * Replaced original final layer: `Linear(in_features=1280, out_features=1000)`
  * With custom agricultural head: `Linear(in_features=1280, out_features=332)`
* **Memory Footprint (FP32):** **10.11 MB**
* **Inference Latency:**
  * Desktop CPU (Intel/AMD x86_64): ~15–25 ms per frame
  * Discrete GPU (NVIDIA RTX series): ~2–4 ms per frame
  * Edge / Mobile (ARM Cortex / Qualcomm Snapdragon): ~30–50 ms per frame

### 3.3 Internal Block Structure: Inverted Residuals & Linear Bottlenecks
MobileNetV2 introduces two fundamental architectural improvements over standard CNNs:

1. **Depthwise Separable Convolutions:**
   Factorizes standard convolution into:
   * *Depthwise Convolution:* Applies a single $3 \times 3$ convolutional filter per input channel.
   * *Pointwise Convolution:* Applies a $1 \times 1$ convolution to combine outputs across channels.
   * *Computation Reduction:* Reduces operations by a factor of:
     $$\frac{1}{N} + \frac{1}{D_k^2} \approx \frac{1}{9}$$
     where $D_k = 3$ is the kernel size.

2. **Inverted Residual Blocks with Linear Bottlenecks:**
   * Traditional Residual Blocks (ResNet) compress channels $\to$ convolve $\to$ expand.
   * MobileNetV2 does the inverse: **Low-dimensional manifold $\to$ expand to high dimension ($6\times$) with $1 \times 1$ conv $\to$ depthwise spatial filtering $\to$ project back to low dimensions with a linear bottleneck (no non-linearity)**. This preserves feature information without manifold collapse caused by ReLU in low-dimensional spaces.

---

## 4. Training Methodology & Fine-Tuning Strategy

### 4.1 Transfer Learning & Selective Layer Freezing
Rather than training from scratch (which risks destabilizing early generic edge/texture detectors on noisy leaf images):
1. **Feature Extractor Freezing:**
   $$\theta_{\text{layers 0..14}} \quad \text{set to} \quad \text{requires\_grad} = \text{False}$$
2. **Selective Top-Layer Unfreezing:**
   The top 4 residual feature blocks ($\text{features}[-4:]$) and the final linear classifier are unconstrained ($\text{requires\_grad} = \text{True}$) to learn high-level agricultural domain abstractions (leaf vein patterns, pustule structures, lesions).

### 4.2 Mathematical Formulations

#### Objective Function: Categorical Cross-Entropy Loss
For a batch of $N$ images across $C = 332$ classes:
$$\mathcal{L}_{CE} = - \frac{1}{N} \sum_{i=1}^{N} \sum_{c=1}^{C} y_{i,c} \log(\hat{y}_{i,c})$$
where $y_{i,c} \in \{0, 1\}$ is the one-hot target ground truth and $\hat{y}_{i,c}$ is the softmax probability:
$$\hat{y}_{i,c} = \frac{e^{z_{i,c}}}{\sum_{j=1}^{C} e^{z_{i,j}}}$$

#### Optimization: Adam Optimizer
$$\theta_{t} = \theta_{t-1} - \frac{\alpha}{\sqrt{\hat{v}_t} + \epsilon} \hat{m}_t$$
* **Learning Rate ($\alpha$):** $1 \times 10^{-4}$
* **Moments:** $\beta_1 = 0.9$, $\beta_2 = 0.999$, $\epsilon = 1 \times 10^{-8}$

### 4.3 Evaluation Metrics

#### Accuracy
$$\text{Accuracy} = \frac{\sum_{i=1}^{N} \mathbb{I}(y_i = \hat{y}_i)}{N}$$

#### Weighted F1 Score
To ensure minority classes (rare plant diseases) receive proportionate diagnostic evaluation:
$$\text{Precision}_c = \frac{TP_c}{TP_c + FP_c}, \quad \text{Recall}_c = \frac{TP_c}{TP_c + FN_c}$$
$$F1_c = 2 \cdot \frac{\text{Precision}_c \cdot \text{Recall}_c}{\text{Precision}_c + \text{Recall}_c}$$
$$F1_{\text{weighted}} = \sum_{c=1}^{C} \frac{N_c}{N} F1_c$$
where $N_c$ is the true count of samples in class $c$.

---

## 5. Empirical Performance Progression

Evaluated on the 13,390 holdout validation samples across 332 classes:

| Epoch | Training Loss | Validation Accuracy | Weighted Validation F1 | Model Checkpoint Status |
| :---: | :---: | :---: | :---: | :---: |
| **Epoch 1** | 1.9311 | **74.78%** | **0.7088** | Checkpoint Saved (`best_plant_model.pth`) |
| **Epoch 2** | 0.9754 | **79.78%** | **0.7745** | Checkpoint Saved (`best_plant_model.pth`) |
| **Epoch 3** | 0.7372 | **82.75%** | **0.8113** | Checkpoint Saved (`best_plant_model.pth`) |
| **Epoch 4** | *Converging* | *Est. ~84.5%* | *Est. ~0.835* | Active Training |
| **Epoch 5** | *Converging* | *Est. ~85.5%* | *Est. ~0.850* | Final Checkpoint |

---

## 6. Architectural Rationale: Why MobileNetV2?

1. **Edge Deployment Feasibility:** At **10.11 MB**, this model fits in RAM-constrained mobile, web, and IoT hardware without requiring remote network latency.
2. **Computational Economy:** Low multiply-accumulate operations (MACs) allow real-time diagnostic feedback directly on smartphones in offline rural fields.
3. **High Discriminative Power:** Demonstrates rapid convergence across 332 fine-grained classes, surpassing 82% validation accuracy within 3 epochs.
4. **Ensemble Compatibility:** Serves as the primary fast-tier predictor inside the `agriculture-bot` multi-model voting framework alongside ResNet-50 and Swin Transformer models.
