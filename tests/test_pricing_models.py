import pytest
from src.pricing_models import calculate_pricing_tier

def test_calculate_pricing_tier():
    # Test data
    customer_data = pd.DataFrame({
        'customer_id': [1, 2, 3],
        'usage': [100, 200, 300]
    })
    # Expected output
    expected_tier = 'basic'
    # Call the function to test
    tier = calculate_pricing_tier(customer_data)
    # Assert the result
    assert tier == expected_tier
