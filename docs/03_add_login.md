# Firebase Authentication Implementation Plan

## Overview
Implement Firebase Authentication with Bearer token validation to secure the Council of Sages API. The system will extract `user_id` from Firebase ID tokens instead of receiving it in request bodies.

## Current State Analysis

### Existing Authentication
- **Current**: No authentication required
- **User ID**: Passed explicitly in request body (`OrchestratorRequest.user_id`)
- **Endpoints**: Single `/orchestrator` endpoint that requires authentication

### Affected Components
1. **Request Models**: `OrchestratorRequest` in `types.py` currently requires `user_id`
2. **Endpoints**: `/orchestrator` endpoint in `resources/orchestrator.py`
3. **Business Logic**: All functions expecting `user_id` parameter
4. **Database**: MongoDB conversations tied to `user_id`

## Implementation Plan

### Phase 1: Dependencies and Configuration

#### 1.1 Add Firebase Dependencies
**File**: `pyproject.toml`
```toml
# Add to dependencies array
"firebase-admin>=6.2.0",
"python-jose[cryptography]>=3.3.0",  # For JWT token verification
```

#### 1.2 Firebase Configuration
**File**: `config.py`
```python
# Add Firebase settings
firebase_project_id: str = Field(
    description="Firebase project ID for authentication"
)
firebase_service_account_key: str | None = Field(
    default=None,
    description="Firebase service account key as JSON string (for environment variables)"
)
```

#### 1.3 Environment Variables
**File**: `.env.example`
```bash
# Add Firebase configuration
FIREBASE_PROJECT_ID=your-project-id

# Firebase Service Account Key - IMPORTANT FORMATTING NOTES:
# 1. This should be the entire service account JSON as a single line string
# 2. Get the JSON from Firebase Console > Project Settings > Service Accounts > Generate new private key
# 3. Copy the entire JSON content and format it as a single line
# 4. The private_key field should contain \n characters (not \\n)
# 5. Do NOT add extra escaping - the JSON parsing will handle newlines correctly
# 6. Make sure there are no actual line breaks in the environment variable value
#
# Example format (replace with your actual service account JSON):
FIREBASE_SERVICE_ACCOUNT_KEY={"type":"service_account","project_id":"your-project","private_key_id":"abc123","private_key":"-----BEGIN PRIVATE KEY-----\nYour_Private_Key_Content_Here\n-----END PRIVATE KEY-----\n","client_email":"firebase-adminsdk-xxxxx@your-project.iam.gserviceaccount.com","client_id":"123456789","auth_uri":"https://accounts.google.com/o/oauth2/auth","token_uri":"https://oauth2.googleapis.com/token","auth_provider_x509_cert_url":"https://www.googleapis.com/oauth2/v1/certs","client_x509_cert_url":"https://www.googleapis.com/robot/v1/metadata/x509/firebase-adminsdk-xxxxx%40your-project.iam.gserviceaccount.com"}
```

### Phase 2: Authentication Infrastructure

#### 2.1 Firebase Service Setup
**New File**: `lib/auth/firebase_auth.py`
```python
import json
import asyncio
from typing import Any, Dict

import firebase_admin
from firebase_admin import auth, credentials
from firebase_admin.auth import ExpiredIdTokenError, InvalidIdTokenError
from fastapi import HTTPException, status
from loguru import logger


class FirebaseAuth:
    """Firebase Authentication service for token verification"""

    def __init__(self, project_id: str, service_account_key: str | None = None):
        """Initialize Firebase Auth

        Args:
            project_id: Firebase project ID
            service_account_key: Service account JSON as string
        """
        self.project_id = project_id
        self._initialize_firebase(service_account_key)

    def _initialize_firebase(self, service_account_key: str | None) -> None:
        """Initialize Firebase Admin SDK"""
        try:
            # Check if Firebase app is already initialized
            try:
                firebase_admin.get_app()
                logger.info("Firebase app already initialized")
                return
            except ValueError:
                # App not initialized, proceed with initialization
                pass

            if service_account_key:
                # Initialize with service account key from environment variable
                service_account_info = json.loads(service_account_key)
                cred = credentials.Certificate(service_account_info)
                firebase_admin.initialize_app(cred, {
                    'projectId': self.project_id,
                })
            else:
                # Initialize with default credentials (for local development)
                # This assumes you have GOOGLE_APPLICATION_CREDENTIALS set
                cred = credentials.ApplicationDefault()
                firebase_admin.initialize_app(cred, {
                    'projectId': self.project_id,
                })

            logger.info(f"Firebase Admin SDK initialized for project: {self.project_id}")

        except Exception as e:
            logger.error(f"Failed to initialize Firebase: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Authentication service initialization failed"
            )

    async def verify_token(self, id_token: str) -> Dict[str, Any]:
        """Verify Firebase ID token and return user claims

        Args:
            id_token: Firebase ID token to verify

        Returns:
            Dict containing user claims from the token

        Raises:
            HTTPException: If token is invalid or expired
        """
        try:
            # Run token verification in thread pool since it's blocking
            decoded_token = await asyncio.to_thread(
                auth.verify_id_token, id_token, check_revoked=True
            )

            logger.debug(f"Token verified for user: {decoded_token.get('uid')}")
            return decoded_token

        except ExpiredIdTokenError:
            logger.warning("Expired Firebase token provided")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired"
            )
        except InvalidIdTokenError as e:
            logger.warning(f"Invalid Firebase token: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token"
            )
        except Exception as e:
            logger.error(f"Token verification failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication failed"
            )

    def get_user_id_from_token(self, decoded_token: Dict[str, Any]) -> str:
        """Extract user_id from verified token claims

        Args:
            decoded_token: Already verified token claims

        Returns:
            User ID from the token

        Raises:
            HTTPException: If user ID is missing from token
        """
        user_id = decoded_token.get('uid')
        if not user_id:
            logger.error("Token missing user ID (uid)")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing user identification"
            )

        return user_id
```

#### 2.2 Authentication Dependency
**New File**: `lib/auth/dependencies.py`
```python
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from loguru import logger

from .firebase_auth import FirebaseAuth
from ...config import config

# Initialize HTTPBearer security scheme
security = HTTPBearer(
    scheme_name="Firebase Bearer Token",
    description="Firebase ID token for authentication"
)

# Global Firebase auth instance (will be set during app startup)
_firebase_auth: FirebaseAuth | None = None


def get_firebase_auth() -> FirebaseAuth:
    """Get the global Firebase auth instance

    Returns:
        FirebaseAuth instance

    Raises:
        HTTPException: If Firebase auth is not initialized
    """
    if _firebase_auth is None:
        logger.error("Firebase authentication not initialized")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service not available"
        )
    return _firebase_auth


def set_firebase_auth(firebase_auth: FirebaseAuth) -> None:
    """Set the global Firebase auth instance (called during app startup)"""
    global _firebase_auth
    _firebase_auth = firebase_auth


async def get_current_user_id(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)]
) -> str:
    """Extract and validate user ID from Firebase Bearer token

    Args:
        credentials: HTTP Bearer credentials from Authorization header

    Returns:
        Verified user ID from Firebase token

    Raises:
        HTTPException: If token is invalid, expired, or missing user ID
    """
    try:
        # Get Firebase auth instance
        firebase_auth = get_firebase_auth()

        # Extract token from credentials
        token = credentials.credentials
        logger.debug("Verifying Firebase token")

        # Verify token with Firebase
        decoded_token = await firebase_auth.verify_token(token)

        # Extract user ID from verified token
        user_id = firebase_auth.get_user_id_from_token(decoded_token)

        logger.debug(f"Authentication successful for user: {user_id}")
        return user_id

    except HTTPException:
        # Re-raise HTTP exceptions (these are already properly formatted)
        raise
    except Exception as e:
        # Log unexpected errors and return generic auth failure
        logger.error(f"Unexpected authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed"
        )

```

#### 2.3 Authentication Exceptions
**File**: `exc.py` (add to existing file or create if doesn't exist)
```python
class AuthenticationError(Exception):
    """Base class for authentication errors"""
    pass


class TokenExpiredError(AuthenticationError):
    """Raised when Firebase token is expired"""
    pass


class InvalidTokenError(AuthenticationError):
    """Raised when Firebase token is invalid"""
    pass


class AuthenticationServiceError(AuthenticationError):
    """Raised when authentication service is unavailable"""
    pass
```

### Phase 3: API Changes

#### 3.1 Update Request Models
**File**: `types.py`
```python
class OrchestratorRequest(BaseModel):
    """Request model for orchestrator endpoint with conversation support"""

    query: str = Field(description="User query to process")
    # Remove user_id field - will be extracted from Bearer token
    conversation_id: str | None = Field(
        default=None,
        description=(
            "Optional conversation ID to continue existing conversation"
        ),
    )
```

#### 3.2 Update Orchestrator Endpoint
**File**: `resources/orchestrator.py`
```python
from typing import Any, Annotated

from fastapi import HTTPException, status, Depends
from fastapi.routing import APIRouter

from ..orchestrator.llm_agent import arun_agent
from ..types import OrchestratorRequest, OrchestratorResponse
from ..lib.auth.dependencies import get_current_user_id

router = APIRouter(tags=["orchestrator"])

DESCRIPTION = (
    "Run the philosophical sage orchestrator with intelligent query "
    "distribution and conversation persistence. Requires Firebase authentication."
)

RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_401_UNAUTHORIZED: {
        "description": "Invalid or missing authentication token",
        "content": {
            "application/json": {
                "example": {"detail": "Invalid authentication token"}
            }
        }
    },
    status.HTTP_403_FORBIDDEN: {
        "description": "Token expired or insufficient permissions",
        "content": {
            "application/json": {
                "example": {"detail": "Token has expired"}
            }
        }
    },
    status.HTTP_422_UNPROCESSABLE_ENTITY: {
        "description": "Invalid input data"
    },
    status.HTTP_500_INTERNAL_SERVER_ERROR: {
        "description": "Orchestrator execution failed"
    },
}


@router.post(
    "/orchestrator",
    status_code=status.HTTP_200_OK,
    response_model=OrchestratorResponse,
    responses=RESPONSES,
    description=DESCRIPTION,
    summary="Run Philosophical Sage Orchestrator",
)
async def run_orchestrator_endpoint(
    request: OrchestratorRequest,
    user_id: Annotated[str, Depends(get_current_user_id)],  # Extract from token
) -> OrchestratorResponse:
    """
    Main endpoint to run the sage orchestrator with conversation persistence.

    **Authentication Required**: This endpoint requires a valid Firebase Bearer token
    in the Authorization header.

    This endpoint:
    1. Validates the Firebase Bearer token and extracts user_id
    2. Receives a user query and optional conversation_id
    3. Retrieves or creates conversation history from MongoDB
    4. Distributes the query intelligently to philosophical sages with
       conversation context
    5. Consolidates the wisdom into a coherent answer
    6. Saves the conversation to MongoDB
    7. Returns the final response with conversation details

    Args:
        request: Request containing query and optional conversation_id
        user_id: Automatically extracted from Firebase Bearer token

    Returns:
        OrchestratorResponse with sage wisdom and conversation details

    Raises:
        HTTPException: 401 for authentication failures, 500 for execution errors
    """
    try:
        # Call the orchestrator sage function with conversation support
        result = await arun_agent(
            query=request.query,
            user_id=user_id,  # Now comes from authenticated token
            conversation_id=request.conversation_id,
        )

        return OrchestratorResponse(
            response=result["final_response"],
            conversation_id=result["conversation_id"],
            agent_queries=result["agent_queries"],
            agent_responses=result["agent_responses"],
        )

    except Exception as e:  # noqa: BLE001
        logger.error(f"Orchestrator execution failed for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sage orchestrator execution failed: {str(e)}",
        )
```

### Phase 4: Application Integration

#### 4.1 Initialize Firebase in App Startup
**File**: `app.py`
```python
import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from pydantic import BaseModel

# Load environment variables from .env file
load_dotenv()

from .config import config
from .lib.database import init_database
from .lib.auth.firebase_auth import FirebaseAuth
from .lib.auth.dependencies import set_firebase_auth
from .resources.orchestrator import router as orchestrator_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Application lifespan manager."""
    # Startup
    logger.info("Starting Council of Sages API...")
    try:
        # Initialize Firebase Authentication
        logger.info("Initializing Firebase authentication...")
        firebase_auth = FirebaseAuth(
            project_id=config.firebase_project_id,
            service_account_key=config.firebase_service_account_key
        )
        set_firebase_auth(firebase_auth)
        logger.info("Firebase authentication initialized successfully")

        # Initialize Database
        await asyncio.to_thread(init_database)
        logger.info("Database initialization completed successfully")

    except Exception as e:
        logger.error(f"Failed to initialize services during startup: {e}")
        raise

    try:
        yield
    finally:
        # Shutdown
        logger.info("Shutting down Council of Sages API...")


app = FastAPI(
    title="Council of Sages",
    description="FastAPI + LangGraph application with Firebase Authentication",
    version="0.1.0",
    lifespan=lifespan,
)

# Configure CORS with explicit Authorization header support
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins,
    allow_credentials=config.cors_allow_credentials,
    allow_methods=config.cors_allow_methods,
    allow_headers=[
        "Accept",
        "Accept-Language",
        "Content-Language",
        "Content-Type",
        "Authorization",  # Explicitly allow Authorization header for Bearer tokens
    ],
)

# Include routers
app.include_router(orchestrator_router)


class HealthResponse(BaseModel):
    status: str
    message: str


class HelloResponse(BaseModel):
    message: str
    name: str


@app.get("/health")
async def health() -> HealthResponse:
    """Health check endpoint"""
    return HealthResponse(status="healthy", message="Service is running")


@app.get("/health/authenticated")
async def authenticated_health(
    user_id: Annotated[str, Depends(get_current_user_id)]
) -> HealthResponse:
    """Authenticated health check endpoint to test Firebase auth"""
    return HealthResponse(
        status="healthy",
        message=f"Authenticated service is running for user: {user_id}"
    )


@app.get("/hello/{name}")
async def hello_world(name: str) -> HelloResponse:
    """Simple hello world endpoint"""
    return HelloResponse(
        message=f"Hello, {name}! Welcome to {config.app_name}", name=name
    )


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint"""
    return {"message": "Welcome to Council of Sages API"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8080, reload=True)
```

#### 4.2 Create lib/auth Directory Structure
**New Directory**: `lib/auth/`
**New File**: `lib/auth/__init__.py`
```python
"""Authentication module for Firebase integration"""

from .firebase_auth import FirebaseAuth
from .dependencies import get_current_user_id, get_current_user_id_optional

__all__ = ["FirebaseAuth", "get_current_user_id"]
```
