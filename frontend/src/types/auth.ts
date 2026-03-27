export type LoginResponse = {
  access_token: string;
  refresh_token: string;
  token_type: string;
};

export type JwtPayload = {
  sub: string;
  typ?: string;
  exp?: number;
};

export type RefreshTokenRequest = {
  refresh_token: string;
};

export type Credentials = {
  username: string;
  password: string;
};
