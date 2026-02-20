#!/usr/bin/env python3
"""Seed the database with sample data for development."""

import asyncio

from kdd_engine.core.models.document import Document


SAMPLE_DOCUMENTS = [
    {
        "title": "User Authentication Entity",
        "domain": "security",
        "tags": ["authentication", "user", "security"],
        "content": """# User Authentication

## Entity: User

A User represents an authenticated individual in the system.

### Attributes

- **id**: Unique identifier (UUID)
- **email**: User's email address (unique)
- **password_hash**: Hashed password
- **created_at**: Account creation timestamp
- **last_login**: Last successful login timestamp

### Business Rules

- BR-001: Email must be unique across all users
- BR-002: Password must be at least 8 characters
- BR-003: Users must verify email before login
""",
    },
    {
        "title": "Order Processing Use Case",
        "domain": "orders",
        "tags": ["order", "processing", "use-case"],
        "content": """# Order Processing

## Use Case: UC-001 Place Order

### Actors
- Customer
- Payment System

### Preconditions
- Customer is authenticated
- Cart contains at least one item

### Main Flow
1. Customer selects checkout
2. System displays order summary
3. Customer confirms order details
4. System validates inventory
5. System processes payment
6. System creates order record
7. System sends confirmation email

### Alternative Flows
- 4a. Insufficient inventory: Notify customer, suggest alternatives
- 5a. Payment fails: Retry or cancel order

### Postconditions
- Order is created in PENDING status
- Inventory is reserved
- Customer receives confirmation
""",
    },
    {
        "title": "Inventory Management Rules",
        "domain": "inventory",
        "tags": ["inventory", "rules", "stock"],
        "content": """# Inventory Management

## Business Rules

### RN-001: Stock Threshold
When product stock falls below the minimum threshold, the system must automatically generate a restock alert.

### RN-002: Reserved Stock
Stock marked as reserved for pending orders cannot be allocated to new orders.

### RN-003: Stock Validation
Before confirming an order, the system must verify that sufficient unreserved stock exists for all items.

### RN-004: Stock Reconciliation
Physical inventory counts must be reconciled with system records monthly.
""",
    },
]


async def seed_data() -> None:
    """Seed the database with sample documents."""
    print("Seeding sample data...")

    # TODO: Initialize services and index documents
    # For now, just print what would be indexed

    for doc_data in SAMPLE_DOCUMENTS:
        doc = Document(
            title=doc_data["title"],
            content=doc_data["content"],
            domain=doc_data["domain"],
            tags=doc_data["tags"],
        )
        print(f"Would index: {doc.title} (domain: {doc.domain})")

    print("\nSeed data prepared. Implement indexing service to actually index.")


if __name__ == "__main__":
    asyncio.run(seed_data())
