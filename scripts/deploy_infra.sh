#!/bin/bash

# ==========================================
# Configuration Variables
# ==========================================
source .env
echo $BUCKET_NAME
SA_NAME="aethelgard-vertex-sa"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
KEY_FILE_NAME="${SA_NAME}-key.json"

echo "Setting active GCP Project to $PROJECT_ID..."
gcloud config set project $PROJECT_ID

echo "Enabling APIs..."
gcloud services enable aiplatform.googleapis.com compute.googleapis.com logging.googleapis.com cloudquotas.googleapis.com


# ==========================================
# 1. Create the Service Account
# ==========================================
echo "Creating Service Account: $SA_NAME..."
gcloud iam service-accounts create $SA_NAME \
    --description="Service Account for Aethelgard MedGemma endpoints" \
    --display-name="Aethelgard Vertex SA"

# ==========================================
# 2. Grant Necessary Roles
# ==========================================
echo "Granting Vertex AI User and Logging roles to the SA..."
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/aiplatform.user"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/logging.logWriter"

# ==========================================
# 3. Create & Save the API Key (JSON Key)
# ==========================================
if [ -f "$KEY_FILE_NAME" ]; then
    echo "✅ API Key already exists locally at ${KEY_FILE_NAME}. Skipping creation to prevent key rotation."
else
    echo "Generating and saving Service Account JSON key to ${KEY_FILE_NAME}..."
    gcloud iam service-accounts keys create $KEY_FILE_NAME \
        --iam-account=$SA_EMAIL

    # Secure the key file locally
    chmod 600 $KEY_FILE_NAME
    echo "✅ API Key successfully saved and secured: $KEY_FILE_NAME"
fi

# 2. Create GCS Buckets
echo "Creating Buckets..."
gcloud storage buckets create "gs://$BUCKET_NAME" --location=$REGION || true

gcloud compute networks subnets update default \
    --region=$REGION \
    --enable-private-ip-google-access

gcloud config set billing/quota_project $PROJECT_ID

echo "=========================================="
echo "Deployment Complete!"
echo "API Key Path: $(pwd)/${KEY_FILE_NAME}"
echo "=========================================="