"""One-time local/hosted organization bootstrap; prints credential only once."""

import argparse
from pathlib import Path

from qsmlops.database.engine import create_engine
from qsmlops.database.migrations import MigrationRunner
from qsmlops.evidence.ledger import EvidenceLedger
from qsmlops.security.audit.service import AuditService
from qsmlops.security.identity.service import IdentityService
from satsa.tenancy import TenantAdministration


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--organization", required=True)
    args = parser.parse_args()
    args.ledger.parent.mkdir(parents=True, exist_ok=True)
    db = create_engine(args.database_url)
    try:
        MigrationRunner(db).migrate()
        with db.transaction():
            guard = db.query_one(
                "SELECT initialized FROM satsa_api_bootstrap WHERE id=1"
                + (" FOR UPDATE" if db.dialect == "postgresql" else "")
            )
            if (
                guard is None
                or guard["initialized"]
                or db.query_one("SELECT id FROM satsa_organizations LIMIT 1")
            ):
                parser.error(
                    "bootstrap is only allowed once, before organization provisioning"
                )
            audit = AuditService(EvidenceLedger(args.ledger), database=db)
            identity_service = IdentityService(db, audit)
            identity = identity_service.create_identity(
                "human", args.name, "SAT-SA platform administration", "satsa_admin"
            )
            admin = TenantAdministration(db)
            organization = admin.create_organization(args.organization)
            user = admin.create_user(identity.id, args.email)
            admin.add_membership(organization, user, "satsa_admin")
            db.execute("UPDATE satsa_api_bootstrap SET initialized=1 WHERE id=1")
        credential = identity_service.issue_credential(identity.id, actor=identity.id)
        print(
            f"organization_id={organization}\nuser_id={user}\nidentity_id={identity.id}"
        )
        print("Store this credential securely; it is displayed once:")
        print(credential)
    finally:
        db.close()


if __name__ == "__main__":
    main()
