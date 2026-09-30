"""Phase 22: security properties of the AWS deployment definition.

Static checks of deploy/aws/satsa.cfn.yaml and deploy/aws/compose.aws.yml, so a
later edit cannot quietly open the database, SSH, or the bucket.
"""

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
AWS = ROOT / "deploy" / "aws"


class _Loader(yaml.SafeLoader):
    pass


def _tag(loader, suffix, node):
    if isinstance(node, yaml.ScalarNode):
        return {f"!{suffix}": loader.construct_scalar(node)}
    if isinstance(node, yaml.SequenceNode):
        return {f"!{suffix}": loader.construct_sequence(node, deep=True)}
    return {f"!{suffix}": loader.construct_mapping(node, deep=True)}


_Loader.add_multi_constructor("!", _tag)


@pytest.fixture(scope="module")
def template():
    return yaml.load((AWS / "satsa.cfn.yaml").read_text("utf-8"), Loader=_Loader)


def _of_type(template, kind):
    return {k: v for k, v in template["Resources"].items() if v["Type"] == kind}


def test_database_is_private_encrypted_backed_up_and_tls_only(template):
    (db,) = _of_type(template, "AWS::RDS::DBInstance").values()
    props = db["Properties"]
    assert props["Engine"] == "postgres" and props["PubliclyAccessible"] is False
    assert props["StorageEncrypted"] is True and props["DeletionProtection"] is True
    assert props["ManageMasterUserPassword"] is True and "MasterUserPassword" not in props
    assert template["Parameters"]["DbEngineVersion"]["Default"].startswith("17")
    assert template["Parameters"]["DbBackupRetentionDays"]["Default"] >= 1
    (params,) = _of_type(template, "AWS::RDS::DBParameterGroup").values()
    assert params["Properties"]["Parameters"]["rds.force_ssl"] == "1"
    sg = template["Resources"]["DatabaseSecurityGroup"]["Properties"]["SecurityGroupIngress"]
    assert all("SourceSecurityGroupId" in rule and "CidrIp" not in rule for rule in sg)


def test_instance_exposes_only_web_ports_and_requires_imdsv2(template):
    ingress = template["Resources"]["InstanceSecurityGroup"]["Properties"]["SecurityGroupIngress"]
    assert {rule["FromPort"] for rule in ingress} == {80, 443}
    (instance,) = _of_type(template, "AWS::EC2::Instance").values()
    meta = instance["Properties"]["MetadataOptions"]
    assert meta["HttpTokens"] == "required" and meta["HttpPutResponseHopLimit"] == 2
    assert "KeyName" not in instance["Properties"]  # no SSH key pair


def test_bucket_is_private_versioned_encrypted_and_tls_only(template):
    bucket = template["Resources"]["EvidenceBucket"]["Properties"]
    assert all(bucket["PublicAccessBlockConfiguration"].values())
    assert bucket["VersioningConfiguration"]["Status"] == "Enabled"
    rule = bucket["BucketEncryption"]["ServerSideEncryptionConfiguration"][0]
    assert rule["ServerSideEncryptionByDefault"]["SSEAlgorithm"] == "aws:kms"
    policy = template["Resources"]["EvidenceBucketPolicy"]["Properties"]["PolicyDocument"]
    assert any(s["Effect"] == "Deny" and "aws:SecureTransport" in str(s) for s in policy["Statement"])
    endpoints = _of_type(template, "AWS::EC2::VPCEndpoint")
    assert any(e["Properties"]["VpcEndpointType"] == "Gateway" for e in endpoints.values())


def test_data_volume_is_separate_encrypted_and_snapshotted(template):
    (volume,) = _of_type(template, "AWS::EC2::Volume").values()
    assert volume["Properties"]["Encrypted"] is True and volume["DeletionPolicy"] == "Snapshot"


def test_roles_are_least_privilege(template):
    role = template["Resources"]["InstanceRole"]["Properties"]
    assert role["ManagedPolicyArns"] == ["arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"]
    text = str(role["Policies"])
    assert "AdministratorAccess" not in text and "'Action': '*'" not in text
    deploy = template["Resources"]["DeployRole"]["Properties"]
    condition = deploy["AssumeRolePolicyDocument"]["Statement"][0]["Condition"]["StringEquals"]
    assert "environment:aws-" in str(condition["token.actions.githubusercontent.com:sub"])


def test_no_secret_material_in_the_stack_definition(template):
    text = (AWS / "satsa.cfn.yaml").read_text("utf-8")
    import re

    for marker in (r"AKIA[0-9A-Z]{16}", r"aws_secret_access_key", r"(?<![A-Za-z])MasterUserPassword:"):
        assert not re.search(marker, text), marker
    for name, parameter in template["Parameters"].items():
        assert "password" not in name.lower() and "secret" not in name.lower()


def test_aws_compose_overlay_uses_rds_tls_role_based_s3_and_ebs():
    overlay = yaml.load((AWS / "compose.aws.yml").read_text("utf-8"), Loader=_Loader)
    backend = overlay["x-aws-backend"]
    env = backend["environment"]
    assert env["SATSA_DB_REQUIRE_VERIFIED_TLS"] == "true"
    assert env["SATSA_S3_ENDPOINT_URL"] == "" and env["SATSA_S3_ACCESS_KEY"] == ""
    volumes = backend["volumes"]["!override"]
    assert "/data/satsa:/data" in volumes
    assert "database" not in overlay["services"]
    assert "${SATSA_IMAGE_TAG" in backend["image"]
