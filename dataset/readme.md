# A Synthetic Multimodal Clinical Dataset for Evaluating Local-First Federated Retrieval-Augmented Generation

## Abstract
Current methodologies for overcoming medical data silos are largely inadequate for the era of generative AI. 
To validate the "Project Aethelgard" Federated RAG architecture, we introduce a highly realistic, synthetic multimodal dataset. 
This dataset is a curated, downsampled subset (N=66) of the [CheXpert dataset](https://stanfordmlgroup.github.io/competitions/chexpert/), 
enriched with generative synthetic clinical admission notes. 
The dataset maps high-fidelity text narratives to confirmed radiographic ground truths, 
physically siloed across multiple simulated environments to evaluate privacy-preserving inference networks.

## Dataset Structure & Schema

The dataset consists of approx 70 patient records distributed across two simulated hospital environments (Hospital_A and Hospital_B) - 
31 patients in cohort A and 35 in cohort B 

* Modality 1 (Visual): Open-access frontal and lateral chest radiographs sourced from CheXpert.

* Modality 2 (Text): Synthetic clinical admission notes generated via MedGemma 27B instructed using a Chain-of-Thought reasoning process.

* Schema (JSON): Each text record conforms to a strict JSON schema containing demographics, clinical_history, 
vitals (including 'red herring' inconsistencies), radiographic_labels, and a hidden_diagnosis_label.

## Disease Selection Rationale

While the Aethelgard architecture is designed to solve the rare disease diagnostic odyssey, for validation purposes, 
we select five highly prevalent and clinically significant pathologies from the CheXpert competition tasks: 
Atelectasis, Cardiomegaly, Consolidation, Edema, and Pleural Effusion.  

Utilizing these validated labels ensures the radiographic ground truth exactly matches the generative clinical presentation.

## 🧬 Synthetic Dataset Generation

Evaluating a privacy-preserving clinical network requires high-fidelity, multimodal data. To safely validate Aethelgard, we generated 
a highly realistic synthetic dataset distributed across our simulated hospital environments. 

The dataset is a curated subset (N=66) of the CheXpert chest X-ray competition dataset. We mapped these open-access images to generative, 
synthetic clinical admission notes. 

### Generation Rationale & Pipeline
We selected five highly prevalent pathologies—Atelectasis, Cardiomegaly, Consolidation, Edema, and Pleural Effusion—to ensure the 
radiographic ground truth perfectly matches the clinical presentation. 

The clinical text was generated using MedGemma 27B. To achieve maximum realism, the model was prompted using a Chain-of-Thought reasoning process. 
Specifically, the prompt (`templates/generate_patient.j2`) instructs the model to act as an expert senior attending physician. 

The prompt engine injects:
* **Patient Demographics**: Age and sex.
* **Radiographic Ground Truth**: Confirmed present, confirmed absent, and uncertain/borderline findings derived directly from the CheXpert labels.

The model is instructed to think step-by-step about the underlying pathophysiology to construct a realistic clinical presentation 
(including History of Present Illness, Review of Systems, and Physical Exam) that precisely aligns with the X-ray. 
It also ensures that generated vitals reflect the severity of the pathology (e.g., severe tachycardia for large consolidations). 

The output is strictly constrained to a structured JSON schema containing the demographics, clinical history, vitals, radiographic labels, 
a hidden diagnosis label, and the full admission note.

## Generate datasets from scratch

A. First we need to lift the limitations for Spot GPUs and A100 models, from 0 -> 1. Lifting limitations on spot resource is optional, 
but lowering the cost.

* Go to the Google Cloud Console in your browser.
* Search for Quotas (IAM & Admin -> Quotas).
* In the Filter bar, paste exactly these metrics: custom_model_serving_nvidia_a100_80gb_gpus, CustomModelServingPreemptibleCPUsPerProjectPerRegion.
  and CustomModelServingPreemptibleA10080GBGPUsPerProjectPerRegion
* Ensure the location is set to us-central1.
* Select the checkbox next to the quota, click Edit Quotas, and request a limit of 1 (or 12 for CustomModelServingPreemptibleCPUsPerProjectPerRegion)

B. Generate a small dataset from CheXpert, using notebook `notebooks/dataset-small.ipynb` and unpack the archive to `.cache/CheXpert`

C. Deploy infra and run pipeline:

```bash
scripts/deploy_infra.sh
gcloud ai models list --region=us-central1
scripts/run_batch_gcp.sh .cache/CheXpert
```

The generated synthetic notes will be saved to /dataset.

To complete the data preparation, we must generate the embeddings for data, using scripts 

```bash
python/generate_embeddings.py --config profiles/node_a.env`
python/generate_embeddings.py --config profiles/node_b.env`
```


## License 

Original source of data: 

CheXpert: A Large Chest X-Ray Dataset And Competition

https://stanfordmlgroup.github.io/competitions/chexpert/

Subset:

https://www.kaggle.com/datasets/ashery/chexpert

Distributed under CC0 1.0 Universal license
