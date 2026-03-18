import * as React from 'react';

import AppBar from '@mui/material/AppBar';
import Box from '@mui/material/Box';
import Toolbar from '@mui/material/Toolbar';
import IconButton from '@mui/material/IconButton';
import Typography from '@mui/material/Typography';
import Menu from '@mui/material/Menu';
import Container from '@mui/material/Container';
import Avatar from '@mui/material/Avatar';
import Tooltip from '@mui/material/Tooltip';
import MenuItem from '@mui/material/MenuItem';
import Link from '@mui/material/Link';

function AppLogo({ href }) {
  const mystyle = {
    height: "130px"
  };

  return (
    <Link href={href} underline="none">
      <img src={require("./logo.png")} style={mystyle} alt="Validation Service - Logo" />
    </Link>
  )
}

const pages = [
  { 
    "label": "Home", 
    "href": "/"
  },
  {
    "label": "Validation",
    "href": "/dashboard"
  },
  { 
    "label": "Logout", 
    "href": "/logout"
  }
]

function ResponsiveAppBar({ user }) {
  
  const [anchorElUser, setAnchorElUser] = React.useState(null);

  const handleOpenUserMenu = (event) => {
    setAnchorElUser(event.currentTarget);
  };

  const handleCloseUserMenu = () => {
    setAnchorElUser(null);
  };

  const styleAppBar = {
    background: 'white',
    color: 'grey',
    borderBottom: "thin solid rgb(238, 238, 238)",
    boxShadow: "none",
    ".MuiToolbar-root": {
      minHeight: '10vh',
    },
    zIndex: (theme) => theme.zIndex.drawer + 1
  };

  return (
    <AppBar position="static" sx={styleAppBar}>
      <Container maxWidth="lg">
        <Toolbar disableGutters>
          <AppLogo href={user ? "/dashboard" : "/"} />
          <Box sx={{ flexGrow: 1 }} />

          {user &&
            <Box sx={{ flexGrow: 0 }}>
              <Tooltip title="Navigation">
                <IconButton onClick={handleOpenUserMenu} sx={{ p: 0 }}>
                  <Avatar
                    sx={{
                      bgcolor: "grey",
                      "&:hover": {
                        border: "2px solid darkgrey",
                      },
                    }}
                  >
                    {Array.from(user["given_name"])[0] + Array.from(user["family_name"])[0]}
                  </Avatar>
                </IconButton>
              </Tooltip>
              <Menu
                sx={{ mt: '45px' }}
                id="menu-appbar"
                anchorEl={anchorElUser}
                anchorOrigin={{
                  vertical: 'top',
                  horizontal: 'right',
                }}
                keepMounted
                transformOrigin={{
                  vertical: 'top',
                  horizontal: 'right',
                }}
                open={Boolean(anchorElUser)}
                onClose={handleCloseUserMenu}
              >
                {pages.map((p) => (
                  <MenuItem key={p.label} onClick={handleCloseUserMenu}>
                    <Link color="grey" href={p.href} underline="none">
                      <Typography textAlign="center">{p.label}</Typography>
                    </Link>
                  </MenuItem>
                ))}
              </Menu>
            </Box>
          }

          {!user &&
            <Box sx={{ flexGrow: 0 }}>
              <Link sx={{
                textDecoration: 'none',
                color: 'black',
                display: 'inline-block',
                border: 'solid 1px black',
                padding: '0.5em 1em',
                borderRadius: '0.5em',
                fontWeight: 'bold',
                '&:hover': {textDecoration: 'underline', color: '#333'}
              }} href="/login">Sign In</Link>
            </Box>
          }
        </Toolbar>
      </Container>
    </AppBar>
  );
}
export default ResponsiveAppBar;
