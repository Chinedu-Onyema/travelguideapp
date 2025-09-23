#!/bin/bash
export TOKEN=`curl -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600"`
export REGION=`curl -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/placement/region`
export DEPLOYMENT_BUCKET=`aws s3api list-buckets --output text --query "Buckets[?starts_with(Name, 'deployment')].Name"`

yum install -y python3.11 python3.11-pip nginx

sudo -u ec2-user -i <<EOF
aws configure set region $REGION
mkdir ~/travelapp
cd ~/travelapp
aws s3 cp s3://$DEPLOYMENT_BUCKET/app.zip /tmp/app.zip
unzip -o /tmp/app.zip
pip3.11 install -r requirements.txt
EOF

# run as sudo
cd /home/ec2-user/travelapp/deployment
KNOWLEDGE_BASE_ID=`aws bedrock-agent list-knowledge-bases --query "knowledgeBaseSummaries[0].knowledgeBaseId" --output text --region $REGION`
# configure service for the application
sed "s/REPLACE_WITH_KNOWLEDGE_BASE_ID/$KNOWLEDGE_BASE_ID/g" travelapp.service > /etc/systemd/system/travelapp.service 
cp travelapp.conf /etc/nginx/conf.d/
# configure nginx
systemctl enable --now travelapp
systemctl enable --now nginx