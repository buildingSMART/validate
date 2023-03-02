import * as React from 'react';
import AppBar from '@mui/material/AppBar';
import Box from '@mui/material/Box';
import Toolbar from '@mui/material/Toolbar';
import IconButton from '@mui/material/IconButton';
import Typography from '@mui/material/Typography';
import Menu from '@mui/material/Menu';
import MenuIcon from '@mui/icons-material/Menu';
import Container from '@mui/material/Container';
import Avatar from '@mui/material/Avatar';
import Button from '@mui/material/Button';
import Tooltip from '@mui/material/Tooltip';
import MenuItem from '@mui/material/MenuItem';
import Link from '@mui/material/Link';

import {PageContext} from './Page';
import { useContext } from 'react';




function AppLogo() {
  const mystyle = {
    height: "60px"
  };

  return (
    <Link href="/" underline="none">
      <img src={require("./BuildingSMART_CMYK_validation_service.png")} style={mystyle} />
    </Link>
  )
}

const pages_ = [{ "label": 'Upload', "href": "/" },
{ "label": "Dashboard",
  "href": "/dashboard"}];

const settings_ = [{ "label": 'Upload new file', "href": "/" },
{ "label": 'Dashboard', "href": "/dashboard" },
{ "label": 'Logout', "href": "/logout" }]

function ResponsiveAppBar({ user }) {
  const [anchorElNav, setAnchorElNav] = React.useState(null);
  const [anchorElUser, setAnchorElUser] = React.useState(null);

    const context = useContext(PageContext);


    let pages;
    let settings;

    if (context.sandboxId){
      pages = [{ "label": 'Upload', "href": `/sandbox/${context.sandboxId}`},
      { "label": "Dashboard",
        "href": `/sandbox/dashboard/${context.sandboxId}`}];
      settings = [{ "label": 'Upload new file', "href": `/sandbox/${context.sandboxId}` },
      { "label": 'Dashboard', "href": `/sandbox/dashboard/${context.sandboxId}`},
      { "label": 'Logout', "href": "/logout" }]
    }else{
      pages = pages_;
      settings = settings_;
    }

  const handleOpenNavMenu = (event) => {
    setAnchorElNav(event.currentTarget);
  };
  const handleOpenUserMenu = (event) => {
    setAnchorElUser(event.currentTarget);
  };

  const handleCloseNavMenu = () => {
    setAnchorElNav(null);
  };

  const handleCloseUserMenu = () => {
    setAnchorElUser(null);
  };

  const styleAppBar = {
    background: 'white',
    color: 'grey',
    borderBottom: "thin solid rgb(238, 238, 238)",
    boxShadow: "none",
    ".MuiToolbar-root" : {
      minHeight: '10vh',
    }
  };

  return (
    <AppBar position="static" sx={styleAppBar}>
      <Container maxWidth="xl">
        <Toolbar disableGutters>
          <Typography
            variant="h6"
            noWrap
            component="a"
            href="/about"
            sx={{
              mr: 2,
              display: { xs: 'none', md: 'flex' },
              fontFamily: 'monospace',
              fontWeight: 700,
              letterSpacing: '.3rem',
              color: 'inherit',
              textDecoration: 'none',
            }}
          >
            <AppLogo />
            <Typography sx={{ display: { xs: 'none', md: 'flex' }, mr: 1 }}>BETA</Typography>
          </Typography>

          <Box sx={{ flexGrow: 1, display: { xs: 'flex', md: 'none' } }}>
            <IconButton
              size="large"
              aria-label="account of current user"
              aria-controls="menu-appbar"
              aria-haspopup="true"
              onClick={handleOpenNavMenu}
              color="inherit"
            >
              <MenuIcon />
            </IconButton>
            <Menu
              id="menu-appbar"
              anchorEl={anchorElNav}
              anchorOrigin={{
                vertical: 'bottom',
                horizontal: 'left',
              }}
              keepMounted
              transformOrigin={{
                vertical: 'top',
                horizontal: 'left',
              }}
              open={Boolean(anchorElNav)}
              onClose={handleCloseNavMenu}
              sx={{
                display: { xs: 'block', md: 'none' },
              }}
            >
              {pages.map((page) => (
                <MenuItem key={page} onClick={handleCloseNavMenu}>
                  <Link href={page["href"]} underline="none">
                    <Typography style={{ color: 'grey' }} textAlign="center">{page["label"]}</Typography>
                  </Link>
                </MenuItem>
              ))}
            </Menu>
          </Box>

          <Typography
            variant="h5"
            noWrap
            component="a"
            href="/about"
            sx={{
              mr: 2,
              display: { xs: 'flex', md: 'none' },
              flexGrow: 1,
              fontFamily: 'monospace',
              fontWeight: 700,
              letterSpacing: '.3rem',
              color: 'inherit',
              textDecoration: 'none',
            }}
          >
            <AppLogo />
            <Typography sx={{ display: { xs: 'flex', md: 'none' }, mr: 1 }}>BETA</Typography>
          </Typography>
          <Box sx={{ flexGrow: 1, display: { xs: 'none', md: 'flex' } }}>
            {pages.map((page) => (
              <Button
                key={page["label"]}
                onClick={handleCloseNavMenu}
                sx={{ my: 2, color: 'grey', display: 'block' }}
              >
                <Link color="inherit" href={page["href"]} underline="none">
                  {page["label"]}
                </Link>
              </Button>
            ))}
          </Box>

          <Box sx={{ flexGrow: 0 }}>
            <Tooltip title="Open settings">
              <IconButton onClick={handleOpenUserMenu} sx={{ p: 0 }}>
                <Avatar sx={{ bgcolor: "grey" }}>
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
              {settings.map((setting) => (
                <MenuItem key={setting["label"]} onClick={handleCloseUserMenu}>
                  <Link color="grey" href={setting["href"]} underline="none">
                    <Typography textAlign="center">{setting["label"]}</Typography>
                  </Link>
                </MenuItem>
              ))}
            </Menu>
          </Box>
        </Toolbar>
      </Container>
    </AppBar>
  );
}
export default ResponsiveAppBar;
