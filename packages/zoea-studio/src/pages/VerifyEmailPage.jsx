/**
 * VerifyEmail Page
 *
 * Handles email verification when users click the link in their verification email.
 * Extracts the verification key from URL query parameters and calls the API.
 */

import { useEffect, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { Loader2, CheckCircle, XCircle } from 'lucide-react';
import api from '../services/api';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';

function VerifyEmailPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [status, setStatus] = useState('verifying'); // 'verifying', 'success', 'error'
  const [message, setMessage] = useState('');
  const [isResending, setIsResending] = useState(false);

  useEffect(() => {
    const verifyEmail = async () => {
      // Get the verification key from URL query parameter
      const key = searchParams.get('key');

      if (!key) {
        setStatus('error');
        setMessage('Invalid verification link. No verification key provided.');
        return;
      }

      try {
        const response = await api.verifyEmail(key);

        if (response.success) {
          setStatus('success');
          setMessage(response.message || 'Email verified successfully. You can now log in.');
        } else {
          setStatus('error');
          setMessage(response.message || 'Verification failed.');
        }
      } catch (err) {
        console.error('Email verification error:', err);
        setStatus('error');
        setMessage(err.message || 'Verification failed. The link may be invalid or expired.');
      }
    };

    verifyEmail();
  }, [searchParams]);

  const handleResendVerification = async () => {
    const email = prompt('Please enter your email address to resend the verification link:');

    if (!email) {
      return;
    }

    setIsResending(true);

    try {
      const response = await api.resendVerification(email);
      if (response.success) {
        alert('Verification email sent! Please check your inbox.');
      }
    } catch (err) {
      console.error('Resend verification error:', err);
      alert(err.message || 'Failed to resend verification email. Please try again.');
    } finally {
      setIsResending(false);
    }
  };

  const handleGoToLogin = () => {
    navigate('/');
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <Card>
          <CardHeader className="text-center">
            <CardTitle className="text-2xl">Email Verification</CardTitle>
            <CardDescription>
              {status === 'verifying' && 'Verifying your email address...'}
              {status === 'success' && 'Verification successful'}
              {status === 'error' && 'Verification failed'}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col gap-6">
              {/* Status Icon and Message */}
              <div className="flex flex-col items-center gap-4">
                {status === 'verifying' && (
                  <Loader2 className="h-16 w-16 text-primary animate-spin" />
                )}
                {status === 'success' && (
                  <CheckCircle className="h-16 w-16 text-green-500" />
                )}
                {status === 'error' && (
                  <XCircle className="h-16 w-16 text-destructive" />
                )}

                {status !== 'verifying' && (
                  <div
                    className={`text-center px-4 py-3 rounded-md text-sm ${
                      status === 'success'
                        ? 'bg-green-500/10 border border-green-500 text-green-700 dark:text-green-400'
                        : 'bg-destructive/10 border border-destructive text-destructive'
                    }`}
                  >
                    {message}
                  </div>
                )}
              </div>

              {/* Action Buttons */}
              {status === 'success' && (
                <Button onClick={handleGoToLogin} className="w-full">
                  Continue to Login
                </Button>
              )}

              {status === 'error' && (
                <div className="flex flex-col gap-3">
                  <Button
                    onClick={handleResendVerification}
                    variant="outline"
                    className="w-full"
                    disabled={isResending}
                  >
                    {isResending ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Sending...
                      </>
                    ) : (
                      'Resend Verification Email'
                    )}
                  </Button>

                  <Button onClick={handleGoToLogin} variant="ghost" className="w-full">
                    Back to Login
                  </Button>
                </div>
              )}

              {/* Help Text */}
              {status === 'error' && (
                <div className="text-center text-sm text-muted-foreground">
                  <p>
                    If you continue to experience issues, please contact support or try
                    registering again.
                  </p>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

export default VerifyEmailPage;
