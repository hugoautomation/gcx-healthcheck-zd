from django.db import migrations

def cleanup_webhook_endpoints(apps, schema_editor):
    """Remove duplicate webhook endpoints before applying dj-stripe migration"""
    WebhookEndpoint = apps.get_model('djstripe', 'WebhookEndpoint')
    db_alias = schema_editor.connection.alias
    
    # Get all webhook endpoints ordered by creation date
    endpoints = WebhookEndpoint.objects.using(db_alias).order_by('created')
    
    # Keep track of seen UUIDs
    seen_uuids = set()
    
    # Remove duplicates while keeping the oldest one
    for endpoint in endpoints:
        if endpoint.djstripe_uuid in seen_uuids:
            endpoint.delete()
        else:
            seen_uuids.add(endpoint.djstripe_uuid)

def reverse_cleanup(apps, schema_editor):
    """No reverse operation needed"""
    pass

class Migration(migrations.Migration):
    dependencies = [
        ('healthcheck', '0001_initial'),  # Changed to depend on your initial migration
        ('djstripe', '__first__'),  # This ensures djstripe tables exist
    ]

    operations = [
        migrations.RunPython(cleanup_webhook_endpoints, reverse_cleanup),
    ]