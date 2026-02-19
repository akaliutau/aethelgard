#!/bin/bash

# ==========================================
# Configuration Variables
# ==========================================
source .env

echo -e "\n=========================================="
echo "1. Sweeping Vertex AI Endpoints"
echo "=========================================="
# Get a list of all endpoint resource names in the region
ENDPOINTS=$(gcloud ai endpoints list --region=$REGION --format="value(name)")

if [ -z "$ENDPOINTS" ]; then
    echo "✅ No active endpoints found."
else
    for ENDPOINT in $ENDPOINTS; do
        echo "Inspecting Endpoint: $ENDPOINT"

        # Extract all deployed model IDs attached to this specific endpoint
        DEPLOYED_MODELS=$(gcloud ai endpoints describe $ENDPOINT --region=$REGION --format="value(deployedModels[].id)" 2>/dev/null)

        # We must undeploy every model before the endpoint can be deleted
        for MODEL_ID in $DEPLOYED_MODELS; do
            if [ -n "$MODEL_ID" ]; then
                echo " -> Undeploying model ID: $MODEL_ID"
                gcloud ai endpoints undeploy-model $ENDPOINT \
                    --region=$REGION \
                    --deployed-model-id=$MODEL_ID \
                    --quiet || true
            fi
        done

        # Now that it is empty, delete the endpoint
        echo " -> Deleting Endpoint..."
        gcloud ai endpoints delete $ENDPOINT --region=$REGION --quiet || true
    done
fi

echo "========================================================="
echo "✅ TEARDOWN COMPLETE. YOUR GCP ENVIRONMENT IS CLEAN."
echo "========================================================="