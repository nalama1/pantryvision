"""
Generates the PantryVision AWS architecture diagram using the `diagrams`
Python library (https://diagrams.mingrammer.com/), which renders official
AWS service icons via Graphviz.

Usage:
    python docs/generate_architecture_diagram.py

Output:
    docs/architecture-diagram.png
"""

from diagrams import Diagram, Cluster, Edge
from diagrams.aws.compute import Lambda
from diagrams.aws.database import Dynamodb
from diagrams.aws.storage import S3
from diagrams.aws.ml import Bedrock
from diagrams.aws.network import APIGateway
from diagrams.aws.security import Cognito
from diagrams.aws.integration import Eventbridge
from diagrams.aws.engagement import SES
from diagrams.aws.management import Cloudwatch
from diagrams.aws.mobile import Amplify
from diagrams.onprem.client import User

graph_attr = {
    "fontsize": "20",
    "bgcolor": "white",
}

with Diagram(
    "PantryVision - AWS Architecture",
    filename="docs/architecture-diagram",
    outformat="png",
    show=False,
    direction="LR",
    graph_attr=graph_attr,
):
    user = User("Household User")

    with Cluster("Frontend"):
        amplify = Amplify("React App\n(AWS Amplify Hosting)")

    cognito = Cognito("Cognito Identity Pool\n(temporary credentials)")
    api_gw = APIGateway("API Gateway\n(REST, SigV4)")

    with Cluster("Backend Lambdas (Python 3.12)"):
        upload_fn = Lambda("upload-product-photo")
        extract_fn = Lambda("extract-product-data")
        save_fn = Lambda("save-product")
        list_fn = Lambda("list-products")

    s3 = S3("Product Images\n(private bucket)")
    bedrock = Bedrock("Amazon Nova Pro\n(AI extraction)")
    dynamodb = Dynamodb("pantryvision-products\n(on-demand)")
    cloudwatch = Cloudwatch("Logs & Metrics")

    with Cluster("Daily Expiration Check"):
        eventbridge = Eventbridge("Daily Schedule")
        check_fn = Lambda("check-expiring-products")
        ses = SES("Alert Email")

    user >> amplify
    amplify >> Edge(label="SigV4-signed requests") >> api_gw
    amplify >> Edge(label="get credentials", style="dashed") >> cognito
    cognito >> Edge(style="dashed", label="temp credentials") >> amplify

    api_gw >> upload_fn >> s3
    api_gw >> extract_fn >> bedrock
    api_gw >> save_fn >> dynamodb
    api_gw >> list_fn >> dynamodb
    extract_fn >> Edge(style="dashed") >> s3

    eventbridge >> check_fn
    check_fn >> Edge(label="scan") >> dynamodb
    check_fn >> Edge(label="send alert") >> ses

    [upload_fn, extract_fn, save_fn, list_fn, check_fn] >> Edge(
        style="dotted", color="gray"
    ) >> cloudwatch

print("Diagram generated at docs/architecture-diagram.png")
