#!/bin/bash

# Find the most recent command invocation
MOST_RECENT_COMMAND_ID=$(aws ssm list-commands \
  --query 'sort_by(Commands, &RequestedDateTime)[-1].CommandId' | jq -r .)

# Check if a command ID was found
if [ "$MOST_RECENT_COMMAND_ID" == "None" ] || [ -z "$MOST_RECENT_COMMAND_ID" ]; then
    echo "No recent command invocations found."
    exit 1
fi

# Retrieve the list of instances that executed the command
INSTANCE_IDS=$(aws ssm list-command-invocations \
  --command-id $MOST_RECENT_COMMAND_ID \
  --query "CommandInvocations[*].InstanceId" \
  --output text)

# Check if instances are found
if [ -z "$INSTANCE_IDS" ]; then
  echo "No instances found for Command ID: $MOST_RECENT_COMMAND_ID"
  exit 1
fi

# Loop through each instance and retrieve StandardOutputContent
for INSTANCE_ID in $INSTANCE_IDS; do
  OUTPUT=$(aws ssm get-command-invocation \
    --command-id "$MOST_RECENT_COMMAND_ID" \
    --instance-id "$INSTANCE_ID" \
    --query "StandardOutputContent" \
    --output text)

  # Display output
  echo "Output from $INSTANCE_ID:"
  echo "$OUTPUT"
  echo "---------------------------------------------"
done
