#!/bin/bash
set -e # Exit immediately if a command exits with a non-zero status

# Check arguments
if [ -z "$1" ]; then
    echo "Usage: ./run_batch_gcp.sh <CheXpert_DATASET_DIR>"
    exit 1
fi

DATASET_DIR="$1"

source .env

echo "=========================================="
echo "1. Running Python Pre-Processing"
echo "=========================================="
python pipeline/preprocess_batch.py --dataset_dir "$DATASET_DIR" --limit 2

# ==========================================
# Configuration Variables
# ==========================================

# The Model Garden CLI uses a slightly different string format (no 'publishers/google/models/')
MODEL_ID="google/medgemma@medgemma-27b-it"

# Generate a unique endpoint name using the process ID ($$) so we can find it later
UNIQUE_ENDPOINT_NAME="ephemeral-medgemma-$$"

# ==========================================
# The Fail-Safe Cleanup Block
# ==========================================
cleanup() {
    echo -e "\n=========================================="
    echo "Initiating Guaranteed Teardown Sequence..."
    echo "=========================================="

    # 1. Dynamically find the endpoint ID created by the Model Garden command
    ENDPOINT_ID=$(gcloud ai endpoints list \
        --region=$REGION \
        --filter="displayName=$UNIQUE_ENDPOINT_NAME" \
        --format="value(name)" | head -n 1)

    if [ -n "$ENDPOINT_ID" ]; then
        # 2. Find the deployed model ID attached to this endpoint
        DEPLOYED_MODEL_ID=$(gcloud ai endpoints describe $ENDPOINT_ID \
            --region=$REGION \
            --format="value(deployedModels[0].id)" 2>/dev/null || echo "")

        if [ -n "$DEPLOYED_MODEL_ID" ]; then
            echo "Undeploying model $DEPLOYED_MODEL_ID..."
            gcloud ai endpoints undeploy-model $ENDPOINT_ID \
                --region=$REGION \
                --deployed-model-id=$DEPLOYED_MODEL_ID \
                --quiet || true
        fi

        # 3. Delete the endpoint
        echo "Deleting endpoint $ENDPOINT_ID..."
        gcloud ai endpoints delete $ENDPOINT_ID \
            --region=$REGION \
            --quiet || true

        echo "✅ Teardown complete!"
    fi
}

# Bind the cleanup function to the EXIT signal
trap cleanup EXIT

# ==========================================
# Deployment & Execution
# ==========================================
echo "Provisioning Endpoint and Deploying MedGemma from Model Garden..."
echo "(Note: Provisioning the A100 GPU takes ~10-15 minutes)"

# The dedicated Model Garden deployment command
# Configuration param must match the GCP settings:
# gcloud  ai model-garden models list-deployment-config --model google/medgemma@medgemma-27b-it

gcloud ai model-garden models deploy \
  --model="$MODEL_ID" \
  --region=$REGION \
  --accept-eula \
  --use-dedicated-endpoint \
  --endpoint-display-name="$UNIQUE_ENDPOINT_NAME" \
  --machine-type="a2-ultragpu-1g" \
  --accelerator-type="NVIDIA_A100_80GB"

echo "✅ Model deployed successfully!"

echo "Fetching provisioned Endpoint details..."

# 1. Query BOTH the Endpoint ID and Dedicated DNS in a single, fast request
OUTPUT=$(gcloud ai endpoints list \
  --region="$REGION" \
  --filter="displayName=$UNIQUE_ENDPOINT_NAME" \
  --format="value(name, dedicatedEndpointDns)" \
  2>/dev/null | head -n 1)

# 2. Parse the output into our two variables
read RAW_ENDPOINT_ID DEDICATED_DOMAIN <<< "$OUTPUT"

# gcloud sometimes returns the fully qualified path (projects/.../endpoints/ID)
# instead of just the ID. 'basename' safely extracts just the final ID string.
ENDPOINT_ID=$(basename "$RAW_ENDPOINT_ID")

if [ -z "$ENDPOINT_ID" ] || [ -z "$DEDICATED_DOMAIN" ]; then
    echo "❌ Failed to retrieve Endpoint details. Did the deployment fail?"
    exit 1
fi

echo "✅ Successfully captured Endpoint ID: $ENDPOINT_ID"
echo "✅ Dedicated Domain retrieved: $DEDICATED_DOMAIN"

echo "=========================================="
echo "2. Submitting Requests to Deployed Endpoint"
echo "=========================================="

# 3. Construct your final Endpoint URL
ENDPOINT_URL="https://${DEDICATED_DOMAIN}/v1/projects/${PROJECT_ID}/locations/${REGION}/endpoints/${ENDPOINT_ID}:predict"

echo "🔗 Full inference URL ready!"

mkdir -p ./cache/batch_output
python pipeline/postprocess_batch.py --dataset_dir "$DATASET_DIR" --endpoint "$ENDPOINT_URL"

echo -e "\n============================"
echo "✅ Batch Inference Complete!"
echo "All predictions saved locally"
echo "================================="
