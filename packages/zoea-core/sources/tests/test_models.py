"""
Tests for Source model.
"""

import pytest
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model

from organizations.models import Organization
from projects.models import Project
from sources.models import Source

User = get_user_model()


@pytest.fixture
def organization(db):
    """Create a test organization."""
    return Organization.objects.create(name='Test Organization')


@pytest.fixture
def user(db, organization):
    """Create a test user in the organization."""
    user = User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpass'
    )
    organization.add_user(user)
    return user


@pytest.fixture
def project(db, organization, user):
    """Create a test project."""
    return Project.objects.create(
        organization=organization,
        name='Test Project',
        working_directory='/tmp/test',
        created_by=user
    )


@pytest.fixture
def temp_dir(tmp_path):
    """Create a temporary directory for testing."""
    return tmp_path


class TestSourceModel:
    """Test Source model functionality."""

    def test_create_source(self, project, temp_dir):
        """Test creating a source."""
        source = Source.objects.create(
            project=project,
            organization=project.organization,
            source_type='local',
            name='Test Source',
            config={'path': str(temp_dir)}
        )

        assert source.id is not None
        assert source.project == project
        assert source.organization == project.organization
        assert source.source_type == 'local'
        assert source.name == 'Test Source'
        assert source.config == {'path': str(temp_dir)}
        assert source.is_active is True

    def test_auto_populate_organization(self, project, temp_dir):
        """Test that organization is auto-populated from project."""
        source = Source.objects.create(
            project=project,
            source_type='local',
            name='Test Source',
            config={'path': str(temp_dir)}
        )

        assert source.organization == project.organization

    def test_unique_name_per_project(self, project, temp_dir):
        """Test that source names must be unique per project."""
        Source.objects.create(
            project=project,
            source_type='local',
            name='Test Source',
            config={'path': str(temp_dir)}
        )

        # Creating another source with same name in same project should fail
        with pytest.raises(Exception):  # IntegrityError
            Source.objects.create(
                project=project,
                source_type='local',
                name='Test Source',
                config={'path': str(temp_dir)}
            )

    def test_validate_organization_matches_project(self, organization, project, temp_dir):
        """Test validation ensures organization matches project."""
        other_org = Organization.objects.create(name='Other Organization')

        source = Source(
            project=project,
            organization=other_org,  # Wrong organization
            source_type='local',
            name='Test Source',
            config={'path': str(temp_dir)}
        )

        with pytest.raises(ValidationError, match="must match project's organization"):
            source.full_clean()

    def test_validate_unknown_source_type(self, project, temp_dir):
        """Test validation fails for unknown source type."""
        source = Source(
            project=project,
            organization=project.organization,
            source_type='unknown',
            name='Test Source',
            config={'path': str(temp_dir)}
        )

        with pytest.raises(ValidationError) as exc_info:
            source.full_clean()

        # Check that the error is about unknown source type
        assert 'Unknown source type' in str(exc_info.value)

    def test_validate_invalid_config(self, project):
        """Test validation fails for invalid source config."""
        source = Source(
            project=project,
            organization=project.organization,
            source_type='local',
            name='Test Source',
            config={}  # Missing 'path'
        )

        with pytest.raises(ValidationError) as exc_info:
            source.full_clean()

        # Check that the error is about invalid configuration
        assert 'Invalid configuration' in str(exc_info.value)

    def test_get_source_instance(self, project, temp_dir):
        """Test getting source implementation instance."""
        source = Source.objects.create(
            project=project,
            source_type='local',
            name='Test Source',
            config={'path': str(temp_dir)}
        )

        instance = source.get_source_instance()

        assert instance is not None
        from sources.local import LocalFileSystemSource
        assert isinstance(instance, LocalFileSystemSource)
        assert instance.config['path'] == str(temp_dir)

    def test_test_connection_success(self, project, temp_dir):
        """Test successful connection test."""
        source = Source.objects.create(
            project=project,
            source_type='local',
            name='Test Source',
            config={'path': str(temp_dir)}
        )

        result = source.test_connection()

        assert result is True
        assert source.last_test_success is True
        assert source.last_test_at is not None

    def test_test_connection_failure(self, project):
        """Test failed connection test."""
        source = Source.objects.create(
            project=project,
            source_type='local',
            name='Test Source',
            config={'path': '/nonexistent/path'}  # Invalid path
        )

        result = source.test_connection()

        assert result is False
        assert source.last_test_success is False
        assert source.last_test_at is not None

    def test_get_display_name(self, project, temp_dir):
        """Test getting display name from source instance."""
        source = Source.objects.create(
            project=project,
            source_type='local',
            name='Test Source',
            config={'path': str(temp_dir)}
        )

        display_name = source.get_display_name()

        assert 'Local Filesystem' in display_name
        assert str(temp_dir) in display_name

    def test_str_method(self, project, temp_dir):
        """Test string representation."""
        source = Source.objects.create(
            project=project,
            source_type='local',
            name='Test Source',
            config={'path': str(temp_dir)}
        )

        assert str(source) == 'Test Source (local, active)'

        source.is_active = False
        source.save()

        assert str(source) == 'Test Source (local, inactive)'

    def test_queryset_for_project(self, project, temp_dir):
        """Test filtering sources by project."""
        source1 = Source.objects.create(
            project=project,
            source_type='local',
            name='Source 1',
            config={'path': str(temp_dir)}
        )

        # Create another project and source
        other_project = Project.objects.create(
            organization=project.organization,
            name='Other Project',
            working_directory='/tmp/other'
        )
        source2 = Source.objects.create(
            project=other_project,
            source_type='local',
            name='Source 2',
            config={'path': str(temp_dir)}
        )

        # Filter by project
        project_sources = Source.objects.for_project(project)

        assert source1 in project_sources
        assert source2 not in project_sources

    def test_queryset_active(self, project, temp_dir):
        """Test filtering to only active sources."""
        active_source = Source.objects.create(
            project=project,
            source_type='local',
            name='Active Source',
            config={'path': str(temp_dir)},
            is_active=True
        )

        inactive_source = Source.objects.create(
            project=project,
            source_type='local',
            name='Inactive Source',
            config={'path': str(temp_dir)},
            is_active=False
        )

        active_sources = Source.objects.active()

        assert active_source in active_sources
        assert inactive_source not in active_sources

    def test_queryset_for_user(self, organization, user, project, temp_dir):
        """Test filtering sources by user's organizations."""
        # Create source in user's organization
        user_source = Source.objects.create(
            project=project,
            source_type='local',
            name='User Source',
            config={'path': str(temp_dir)}
        )

        # Create another organization and source
        other_org = Organization.objects.create(name='Other Organization')
        other_project = Project.objects.create(
            organization=other_org,
            name='Other Project',
            working_directory='/tmp/other'
        )
        other_source = Source.objects.create(
            project=other_project,
            source_type='local',
            name='Other Source',
            config={'path': str(temp_dir)}
        )

        # Filter by user
        user_sources = Source.objects.for_user(user)

        assert user_source in user_sources
        assert other_source not in user_sources
