"""Phase 23: one authoritative release identifier (the Git commit) end to end."""

from pathlib import Path

pytest_plugins = ["test_tenant_schema", "test_phase6_api"]

ROOT = Path(__file__).resolve().parents[1]


def test_liveness_reports_the_release_the_image_was_built_from(api, monkeypatch):
    monkeypatch.setenv("SATSA_RELEASE", "92075e8b41919f0b84cc05c03b1f7357b0447ab0")
    body = api["client"].get("/health/live").json()
    assert body == {"status": "alive", "release": "92075e8b41919f0b84cc05c03b1f7357b0447ab0"}


def test_an_unpublished_build_says_so(api, monkeypatch):
    monkeypatch.delenv("SATSA_RELEASE", raising=False)
    assert api["client"].get("/health/live").json()["release"] == "unreleased"


def test_published_images_carry_the_commit():
    publish = (ROOT / "deploy/aws/publish.sh").read_text(encoding="utf-8")
    assert '--build-arg "SATSA_RELEASE=$COMMIT"' in publish
    for dockerfile in ("Dockerfile", "web/Dockerfile"):
        text = (ROOT / dockerfile).read_text(encoding="utf-8")
        assert "ARG SATSA_RELEASE=unreleased" in text
        assert "SATSA_RELEASE=${SATSA_RELEASE}" in text


def test_custom_domain_is_read_at_deploy_time_not_baked_into_the_instance():
    template = (ROOT / "deploy/aws/satsa.cfn.yaml").read_text(encoding="utf-8")
    user_data = template.split("UserData:", 1)[1].split("EipAssociation:", 1)[0]
    site = [line for line in user_data.splitlines() if line.strip().startswith("- Site:")]
    # Only the Elastic IP name: changing SiteAddress must not touch the instance.
    assert len(site) == 1 and "SiteAddress" not in site[0]
    assert 'Name: !Sub "/satsa/${EnvironmentName}/site-address"' in template
    deploy = (ROOT / "deploy/aws/deploy.sh").read_text(encoding="utf-8")
    assert '/satsa/$SATSA_ENV_NAME/site-address' in deploy
    assert "SATSA_SITE_ALIASES=$SATSA_SITE_ADDRESS" in deploy
    caddy = (ROOT / "deploy/caddy/site.caddy").read_text(encoding="utf-8")
    assert "{$SATSA_SITE_ADDRESS} {$SATSA_SITE_ALIASES} {" in caddy
